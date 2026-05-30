import io
import time
import numpy as np
import pandas as pd
import boto3
import argparse
from sklearn.preprocessing import LabelEncoder
from numba import njit


@njit
def assign_splits(group_starts, group_sizes, n_samples):
    assignments = np.zeros(n_samples, dtype=np.int64)
    n_groups = len(group_starts)
    for g in range(n_groups):
        start = group_starts[g]
        size = group_sizes[g]

        if size == 1:
            assignments[start] = 2

        elif size == 2:
            assignments[start]     = 1
            assignments[start + 1] = 2

        elif size == 3:
            assignments[start]     = 0
            assignments[start + 1] = 1
            assignments[start + 2] = 2

        else:
            n_test  = max(1, int(size * 0.1))
            n_val   = max(1, int(size * 0.1))
            n_train = size - n_val - n_test

            for i in range(n_train):
                assignments[start + i] = 0
            for i in range(n_val):
                assignments[start + n_train + i] = 1
            for i in range(n_test):
                assignments[start + n_train + n_val + i] = 2

    return assignments


def naive_assign_splits(group_starts, group_sizes, n_samples):
    """Version Python pure sans Numba — pour comparer les temps"""
    assignments = np.zeros(n_samples, dtype=np.int64)
    for g in range(len(group_starts)):
        start = group_starts[g]
        size  = group_sizes[g]

        if size == 1:
            assignments[start] = 2
        elif size == 2:
            assignments[start]     = 1
            assignments[start + 1] = 2
        elif size == 3:
            assignments[start]     = 0
            assignments[start + 1] = 1
            assignments[start + 2] = 2
        else:
            n_test  = max(1, int(size * 0.1))
            n_val   = max(1, int(size * 0.1))
            n_train = size - n_val - n_test
            for i in range(n_train):
                assignments[start + i] = 0
            for i in range(n_val):
                assignments[start + n_train + i] = 1
            for i in range(n_test):
                assignments[start + n_train + n_val + i] = 2

    return assignments


def preprocess_to_staging(bucket_raw, bucket_staging, input_file, output_prefix):
    s3 = boto3.client('s3', endpoint_url='http://localhost:4566')

    # Step 1: download from S3
    response = s3.get_object(Bucket=bucket_raw, Key=input_file)
    data = pd.read_csv(io.BytesIO(response['Body'].read()))

    # Step 2: clean
    data = data.dropna()

    # Step 3: encode labels
    label_encoder = LabelEncoder()
    data['class_encoded'] = label_encoder.fit_transform(data['family_accession'])

    # Step 4: sort by class
    data_sorted = data.sort_values('class_encoded').reset_index(drop=True)

    # Step 5: compute group boundaries
    class_ids = data_sorted['class_encoded'].values
    unique_classes, counts = np.unique(class_ids, return_counts=True)
    starts = (np.cumsum(counts) - counts).astype(np.int64)
    counts = counts.astype(np.int64)

    # Step 6: numba warm-up + split
    _ = assign_splits(starts[:10], counts[:10], int(counts[:10].sum()))

    start_time = time.perf_counter()
    assignments = assign_splits(starts, counts, len(data_sorted))
    t_numba = time.perf_counter() - start_time
    print(f"Numba split  : {t_numba:.3f}s")

    # Step 7: comparaison avec version naïve
    start_time = time.perf_counter()
    naive_assign_splits(starts, counts, len(data_sorted))
    t_naive = time.perf_counter() - start_time
    print(f"Python naive : {t_naive:.3f}s")
    print(f"Speedup      : {t_naive / t_numba:.1f}x")

    # Step 8: split DataFrame
    train_data = data_sorted[assignments == 0].drop(
        columns=["family_id", "sequence_name", "family_accession"])
    dev_data   = data_sorted[assignments == 1].drop(
        columns=["family_id", "sequence_name", "family_accession"])
    test_data  = data_sorted[assignments == 2].drop(
        columns=["family_id", "sequence_name", "family_accession"])

    print(f"Train: {len(train_data)}, Dev: {len(dev_data)}, Test: {len(test_data)}")

    # Step 9: upload train/dev/test
    for name, df in [("train", train_data), ("dev", dev_data), ("test", test_data)]:
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        s3.put_object(
            Bucket=bucket_staging,
            Key=f"{output_prefix}_{name}.csv",
            Body=buf.getvalue()
        )
        print(f"{name} uploadé dans staging.")

    # Upload label mapping
    label_mapping = dict(zip(
        label_encoder.classes_,
        label_encoder.transform(label_encoder.classes_).tolist()
    ))
    s3.put_object(
        Bucket=bucket_staging,
        Key=f"{output_prefix}_label_mapping.json",
        Body=str(label_mapping)
    )

    # Upload class weights
    class_counts = data_sorted['class_encoded'].value_counts().sort_index()
    class_weights = (1 / class_counts / (1 / class_counts).sum()).to_dict()
    s3.put_object(
        Bucket=bucket_staging,
        Key=f"{output_prefix}_class_weights.json",
        Body=str(class_weights)
    )
    print("Métadonnées uploadées dans staging.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket_raw",     default="raw")
    parser.add_argument("--bucket_staging", default="staging")
    parser.add_argument("--input_file",     default="combined_raw.csv")
    parser.add_argument("--output_prefix",  default="preprocessed")
    args = parser.parse_args()

    preprocess_to_staging(
        args.bucket_raw,
        args.bucket_staging,
        args.input_file,
        args.output_prefix
    )