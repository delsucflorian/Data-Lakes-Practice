from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': True,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

dag = DAG(
    'hackernews_pipeline',
    default_args=default_args,
    description='A simple HackerNews pipeline',
    schedule=timedelta(minutes=5),
)

# Chemin vers les scripts
SCRIPTS_PATH = "/opt/airflow/scripts"

# Tâche pour récupérer et sauvegarder les stories dans S3
fetch_stories = BashOperator(
    task_id='fetch_stories',
    bash_command=f'python {SCRIPTS_PATH}/hn_api.py --limit 50 --endpoint-url http://localstack:4566',
    dag=dag,
)

# Tâche pour indexer dans Elasticsearch
index_stories = BashOperator(
    task_id='index_stories',
    bash_command=f'python {SCRIPTS_PATH}/es_handler.py --host elasticsearch --port 9200 --endpoint-url http://localstack:4566',
    dag=dag,
)

# Définition de l'ordre des tâches
fetch_stories >> index_stories