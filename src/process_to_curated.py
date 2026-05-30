import io
import time
import argparse
import pandas as pd
import boto3
from transformers import AutoTokenizer


def process_to_curated(bucket_staging, bucket_curated, input_file, output_file, batch_size=512):
    s3 = boto3.client('s3', endpoint_url='http://localhost:4566')

    # Step 1: download from staging
    response = s3.get_object(Bucket=bucket_staging, Key=input_file)
    data = pd.read_csv(io.BytesIO(response['Body'].read()))
    sequences = data['sequence'].tolist()
    print(f"{len(sequences)} séquences chargées depuis staging.")

    # Step 2: load tokenizer
    tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t6_8M_UR50D")
    print("Tokenizer chargé.")

    # Step 3: tokenisation séquentielle (sur les 1000 premières)
    subset = sequences[:1000]
    start = time.perf_counter()
    for seq in subset:
        tokenizer(seq, padding=True, truncation=True, max_length=512)
    t_seq = time.perf_counter() - start
    # Step 4: tokenisation par batch (sur les 1000 premières)
    start = time.perf_counter()
    for i in range(0, len(subset), batch_size):
        batch = subset[i:i+batch_size]
        tokenizer(batch, padding=True, truncation=True, max_length=512)
    t_batch = time.perf_counter() - start
    # Step 5: print comparison
    print(f"Sequentiel (1000 seq) : {t_seq:.2f}s")
    print(f"Batch (1000 seq) : {t_batch:.2f}s")
    print(f"Speedup : {t_seq/t_batch:.1f}x")

    all_input_ids = []
    for i in range(0, len(sequences), batch_size):
        batch = sequences[i:i+batch_size]
        encodings = tokenizer(batch, padding=True, truncation=True, max_length=512)
        all_input_ids.extend(encodings['input_ids'])
    
    #Step 7: add to DataFrame
    data['input_ids'] = all_input_ids

    #Step 8 : upload to curated
    output_buffer = io.StringIO()   
    s3.put_object(Bucket=bucket_curated, Key=output_file, Body=data.to_csv(index=False, sep=";"))
    print(f"Fichier correctement téléversé sur LocalStack S3 (Bucket: '{bucket_curated}')")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket_staging", type=str, default="staging")
    parser.add_argument("--bucket_curated", type=str, default="curated")
    parser.add_argument("--input_file",     type=str, default="preprocessed_train.csv")
    parser.add_argument("--output_file",    type=str, default="tokenized_train.csv")
    parser.add_argument("--batch_size",     type=int, default=512)
    args = parser.parse_args()

    process_to_curated(
        args.bucket_staging,
        args.bucket_curated,
        args.input_file,
        args.output_file,
        args.batch_size
    )