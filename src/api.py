import json
import os
from datetime import datetime
from typing import Optional

import boto3
import botocore
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="Data Lake API Gateway",
    description="API Gateway pour les couches Raw (S3), Staging (MySQL) et Curated (MongoDB)",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION            = os.getenv("AWS_REGION", "eu-west-1")
S3_BUCKET_NAME        = os.getenv("S3_BUCKET_NAME")
S3_ENDPOINT_URL       = os.getenv("S3_ENDPOINT_URL")
MONGO_URI            = os.getenv("MONGO_URI")


# ---------------------------------------------------------------------------
# Client S3 (singleton léger)
# ---------------------------------------------------------------------------

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,        # ← ajouter (None en prod = vrai AWS)
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )

# ---------------------------------------------------------------------------
# Exercice 1 — /health
# ---------------------------------------------------------------------------

class ServiceStatus(BaseModel):
    status: str          # "ok" | "error"
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    api_status: str
    timestamp: str
    connections: dict[str, ServiceStatus]


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check():
    connections: dict[str, ServiceStatus] = {}
    # — S3 —
    try:
        s3 = get_s3_client()
        s3.head_bucket(Bucket=S3_BUCKET_NAME)
        connections["s3"] = ServiceStatus(status="ok")
    except botocore.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        connections["s3"] = ServiceStatus(status="error", detail=f"ClientError {code}")
    except Exception as e:
        connections["s3"] = ServiceStatus(status="error", detail=str(e))

    # — MySQL —
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
            connection_timeout=3,
        )
        conn.close()
        connections["mysql"] = ServiceStatus(status="ok")
    except Exception as e:
        connections["mysql"] = ServiceStatus(status="error", detail=str(e))

    # — MongoDB —
    try:
        from pymongo import MongoClient
        from pymongo.errors import ServerSelectionTimeoutError
        client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        client.close()
        connections["mongodb"] = ServiceStatus(status="ok")
    except Exception as e:
        connections["mongodb"] = ServiceStatus(status="error", detail=str(e))

    return HealthResponse(
        api_status="online",
        timestamp=datetime.utcnow().isoformat() + "Z",
        connections=connections,
    )


# ---------------------------------------------------------------------------
# Exercice 2 — /raw/  (couche S3)
# ---------------------------------------------------------------------------

class S3ObjectMeta(BaseModel):
    key: str
    size_bytes: int
    last_modified: str


class RawListResponse(BaseModel):
    bucket: str
    prefix: str
    total_returned: int
    objects: list[S3ObjectMeta]


class RawDataResponse(BaseModel):
    bucket: str
    key: str
    data: list[dict] | dict   # JSON brut du fichier


@app.get("/raw/", response_model=RawListResponse, tags=["Raw — S3"])
async def list_raw_objects(
    prefix: str = Query(default="", description="Préfixe S3 pour filtrer les objets (ex: 'data/2024/')"),
    limit: int  = Query(default=10, ge=1, le=1000, description="Nombre max d'objets retournés"),
):
    """
    Liste les objets JSON dans le bucket S3.
    - **prefix** : filtre par chemin/préfixe
    - **limit**  : plafond de résultats (1–1000)
    """
    try:
        s3 = get_s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix,
            PaginationConfig={"MaxItems": limit},
        )

        objects: list[S3ObjectMeta] = []
        for page in pages:
            for obj in page.get("Contents", []):
                objects.append(
                    S3ObjectMeta(
                        key=obj["Key"],
                        size_bytes=obj["Size"],
                        last_modified=obj["LastModified"].isoformat(),
                    )
                )

        return RawListResponse(
            bucket=S3_BUCKET_NAME,
            prefix=prefix,
            total_returned=len(objects),
            objects=objects,
        )

    except botocore.exceptions.ClientError as e:
        raise HTTPException(status_code=502, detail=f"Erreur S3 : {e.response['Error']['Message']}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/raw/{file_key:path}", response_model=RawDataResponse, tags=["Raw — S3"])
async def get_raw_object(
    file_key: str,
):
    """
    Retourne le contenu JSON d'un fichier S3 par sa clé complète.
    Ex : `/raw/data/2024/records.json`
    """
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=file_key)
        body = response["Body"].read().decode("utf-8")
        data = json.loads(body)

        return RawDataResponse(
            bucket=S3_BUCKET_NAME,
            key=file_key,
            data=data,
        )

    except botocore.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        status = 404 if code == "NoSuchKey" else 502
        raise HTTPException(status_code=status, detail=f"Erreur S3 [{code}] : {e.response['Error']['Message']}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Fichier non parseable en JSON : {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Exercice 3 — /staging/ (couche MySQL)
mysql_config = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3307)),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "root"),
    "database": os.getenv("MYSQL_DATABASE", "staging"),
} 
@app.get("/staging/", tags=["Staging - MySQL"])
#configurer la connexion à MySQL via les variables d'environnement
async def list_staging_records(split: Optional[str] = Query(default=None, description="Filtre par split (ex: 'train', 'test', 'validation')" ),
                               limit: int = Query(default=100, ge=1, le=1000)
) -> dict:
    """
    Liste les enregistrements de la table `texts` dans MySQL.
    retourne un JSON avec le nombre total d'enregistrements et une liste d'objets {id, text}.
    - **split** : filtre par split (train/test/validation)
    - **limit** : plafond de résultats (1–1000)
    """
    try:
        import mysql.connector
        conn = mysql.connector.connect(**mysql_config)
        cur = conn.cursor(dictionary=True)
        if split:
            cur.execute("SELECT id, text, split FROM texts WHERE split = %s LIMIT %s", (split, limit))
        else : 
            cur.execute("SELECT id, text, split FROM texts LIMIT %s", (limit,))
        rows = cur.fetchall()
        conn.close()
        return {"total": len(rows), "records": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/curated/", tags=["Curated - MongoDB"])
async def list_curated_records(limit: Optional[int] = Query(default=100, ge=1, le=1000)) -> dict:
    import pymongo
    client = pymongo.MongoClient("mongodb://localhost:27017/",
                                     serverSelectionTimeoutMS=3000)
    client.server_info()
    db = client["curated"]
    if limit:
        records = list(db["wikitext"].find({}, {"_id": 0, "original_id": 1, "text": 1, "num_tokens": 1 }).limit(limit))
    else:
        records = list(db["wikitext"].find({}, {"_id": 0, "id": 1, "text": 1}))
    client.close()
    return {"total": len(records), "records": records}


@app.get("/totalCurated/", tags=["Curated - total"])
async def total_curated_records() -> int:
    import pymongo
    client = pymongo.MongoClient("mongodb://localhost:27017/",
                                    serverSelectionTimeoutMS=3000)
    client.server_info()
    db = client["curated"]
    total = db["wikitext"].count_documents({})
    client.close()
    return total