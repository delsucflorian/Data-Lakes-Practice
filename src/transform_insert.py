import json 
from datetime import datetime
import boto3
from elasticsearch import Elasticsearch


es = Elasticsearch("http://localhost:9200")
# Cette fonction prend en entrée une liste de stories au format JSON et retourne une liste de stories transformées avec les champs souhaités.
def transform(json) : 
    transformed = []
    for story in json :
        transformed.append({
            "id": story.get("id"),
            "title": story.get("title"),
            "url": story.get("url", ""),
            "score": story.get("score", 0),
            "timestamp": datetime.fromtimestamp(story.get("time", 0)).isoformat()
        })
    return transformed

# Connexion S3 LocalStack
s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1"
)

def read_from_s3():
    response = s3.get_object(Bucket="raw", Key="hackernews/articles.json")
    content = response["Body"].read().decode("utf-8")
    return json.loads(content)

#Insertion dans Elasticsearch
def insert_to_es(documents):
    for doc in documents:
        es.index(
            index="hackernews",  
            id=doc["id"], 
            document=doc
        )
    print(f"✅ {len(documents)} documents insérés dans Elasticsearch")

if __name__ == "__main__":
    stories  = read_from_s3()
    documents = transform(stories)
    insert_to_es(documents)
