from airflow import DAG
import sys 
from airflow.operators.python_operator import PythonOperator
import boto3
from datetime import datetime, timedelta
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/src') 
import src.load_to_staging as load_to_staging
import src.staging_to_curated as staging_to_curated
import json
from transformers import AutoTokenizer

S3_ENDPOINT   = "http://localstack:4566"
S3_BUCKET     = "wikitext-bucket"
AWS_ACCESS_KEY = "test"   # LocalStack accepte n'importe quelle valeur
AWS_SECRET_KEY = "test"
AWS_REGION     = "us-east-1"

def get_s3_client():
    """Retourne un client boto3 pointant vers LocalStack."""
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
    )

def ensure_bucket(s3_client: boto3.client) -> None:
    """Crée le bucket S3 s'il n'existe pas encore."""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET)
    except s3_client.exceptions.NoSuchBucket:
        s3_client.create_bucket(Bucket=S3_BUCKET)
    except Exception:
        # head_bucket lève une ClientError générique si le bucket est absent
        s3_client.create_bucket(Bucket=S3_BUCKET)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
}
def extract(**kwargs): 
    print("Extraction du dataset Wikitext-2 ")
    dataset = load_to_staging.download_wikitext()
    if dataset is None:
        print("Erreur lors du chargement du dataset.")
    s3 = get_s3_client()
    ensure_bucket(s3)
 
    for split in ['train', 'validation', 'test']:
        rows = [{"text": row["text"]} for row in dataset[split]]
        key  = f"raw/{split}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(rows, ensure_ascii=False).encode("utf-8"),
        )
        print(f"  ✓ {len(rows)} lignes uploadées → s3://{S3_BUCKET}/{key}")
 
    # Seul le préfixe transite par XCom (quelques octets)
    return "raw"

def transform(**kwargs) -> str: 
    print("Nettoyage des données...")
    ti = kwargs['ti']
    raw_prefix = ti.xcom_pull(task_ids='extract')
    s3 = get_s3_client()
    
    cleaned_data = {}
    for split in ['train', 'validation', 'test']:
       # Lecture depuis S3
        obj      = s3.get_object(Bucket=S3_BUCKET, Key=f"{raw_prefix}/{split}.json")
        raw_rows = json.loads(obj["Body"].read().decode("utf-8"))
 
        # Nettoyage via la fonction existante (attend une liste de dicts)
        cleaned = load_to_staging.clean_split(raw_rows)
        print(f"  ✓ {len(cleaned)} lignes conservées pour '{split}'")
 
        # Écriture du résultat nettoyé
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"cleaned/{split}.json",
            Body=json.dumps(cleaned, ensure_ascii=False).encode("utf-8"),
        )
 
    return "cleaned"

def import_to_mysql(**kwargs) -> None:
    ti             = kwargs["ti"]
    clean_prefix   = ti.xcom_pull(task_ids="transform")   # == "cleaned"
 
    print("Importation dans MySQL (staging)...")
    s3 = get_s3_client()
 
    connection = load_to_staging.create_mysql_connection("mysql", "root", "root", "staging",port = 3306)
    if connection is None:
        raise ConnectionError("Impossible de se connecter à MySQL.")
 
    load_to_staging.create_table(connection)
 
    for split in ['train', 'validation', 'test']:
        obj     = s3.get_object(Bucket=S3_BUCKET, Key=f"{clean_prefix}/{split}.json")
        rows    = json.loads(obj["Body"].read().decode("utf-8"))
        load_to_staging.insert_data(connection, rows, split)
        print(f"  ✓ {len(rows)} lignes insérées pour '{split}'")
 
    connection.close()
    print("Importation terminée.")
    
def tokenisation_and_import_to_mongodb(**kwargs):
    print("Tokenisation et importation dans MongoDB...")
    train_data = staging_to_curated.get_staging_data("mysql", "root", "root", "staging", "train", port = 3306)
    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    text = [row[1] for row in train_data]
    tokenized = staging_to_curated.tokenize_texts(text, tokenizer, 512)
    documents = staging_to_curated.prepare_documents(train_data, tokenized, "train", "distilbert-base-uncased", 512)
    staging_to_curated.insert_to_mongodb(documents, "mongodb://mongodb:27017/")
    print("Tokenisation et importation terminée.")
    return

with DAG('data_lake_pipeline', default_args=default_args, schedule_interval=None) as dag:
    
    extract_task = PythonOperator(task_id='extract', python_callable=extract)
    transform_task = PythonOperator(task_id='transform', python_callable=transform)
    import_mysql_task = PythonOperator(task_id='import_to_mysql', python_callable=import_to_mysql)  
    tokenisation_import_task = PythonOperator(task_id='tokenisation_and_import_to_mongodb', python_callable=tokenisation_and_import_to_mongodb)

    extract_task >> transform_task >> import_mysql_task >> tokenisation_import_task
