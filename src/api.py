import requests
import json
import argparse
import boto3

# Connexion à LocalStack
s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1"
)

def fetch_articles(n):
    ids = requests.get(
        "https://hacker-news.firebaseio.com/v0/topstories.json"
    ).json()[:n]

    articles = []
    for id in ids:
        art = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{id}.json"
        ).json()
        if art and art.get("type") == "story":
            articles.append(art)
    return articles

def upload_to_s3(articles):
    content = json.dumps(articles, indent=2)

    s3.put_object(
        Bucket="raw",
        Key="hackernews/articles.json",  # chemin dans le bucket
        Body=content,
        ContentType="application/json"
    )
    print(f"✅ {len(articles)} articles uploadés dans s3://raw/hackernews/articles.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args()

    articles = fetch_articles(args.n)
    upload_to_s3(articles)