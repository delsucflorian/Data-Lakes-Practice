"""
seed_raw.py — Dépose un échantillon de WikiText en JSON dans le bucket S3 (raw).
Lit quelques lignes depuis MySQL staging et les pousse vers LocalStack.
"""
import json
import os

import boto3
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "raw")

# --- Récupère un échantillon depuis MySQL ---
conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    port=int(os.getenv("MYSQL_PORT", 3307)),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", "root"),
    database=os.getenv("MYSQL_DATABASE", "staging"),
)
cur = conn.cursor(dictionary=True)
cur.execute("SELECT id, text, split FROM texts WHERE split = 'train' LIMIT 100")
rows = cur.fetchall()
conn.close()

# --- Pousse vers S3 ---
s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

key = "wikitext/train_sample.json"
s3.put_object(
    Bucket=S3_BUCKET_NAME,
    Key=key,
    Body=json.dumps(rows, ensure_ascii=False).encode("utf-8"),
    ContentType="application/json",
)

print(f"OK : {len(rows)} enregistrements poussés dans s3://{S3_BUCKET_NAME}/{key}")
