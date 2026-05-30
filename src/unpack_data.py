import time
import argparse
from pathlib import Path
import pandas as pd
import boto3
from concurrent.futures import ThreadPoolExecutor

# Définition de la fonction requise par le sujet (à adapter selon votre logique exacte)
def read_single_csv(file_path: Path) -> pd.DataFrame:
    # Lecture du fichier CSV individuel
    return pd.read_csv(file_path, sep=";")

def unpack_data(input_dir, output_file, bucket_name="raw", max_workers=4):
    input_path = Path(input_dir)
    output_path = Path(output_file)

    # Step 1: Collecte de tous les fichiers dans une liste unique aplatie
    csv_files = []
    for directory in (d for d in input_path.iterdir() if d.is_dir()):
        csv_files.extend([f for f in directory.iterdir() if f.is_file() and not f.name.startswith('.')])
        
    print(f"Found {len(csv_files)} files to process.")

    # Step 2: sequential reading + timing
    start = time.perf_counter()
    dataframes_seq = []
    for file in csv_files:
        dataframes_seq.append(read_single_csv(file))
    t_sequential = time.perf_counter() - start

    # Step 3: parallel reading + timing
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        dataframes_par = list(executor.map(read_single_csv, csv_files))
    t_parallel = time.perf_counter() - start

    # Step 4: print comparison
    print(f"Sequentiel : {t_sequential:.2f}s")
    print(f"Parallele : {t_parallel:.2f}s")
    if t_parallel > 0:
        print(f"Speedup : {t_sequential / t_parallel:.2f}x")

    # Step 5: Concaténation globale (on utilise les données chargées en parallèle)
    all_data = pd.concat(dataframes_par, ignore_index=True)

    # Step 6: Création de l'arborescence et sauvegarde locale
    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_data.to_csv(output_path, index=False, sep=";")
    print(f"Dataset local sauvegardé dans : {output_path}")
    
    # Step 7: Transfert vers l'infrastructure LocalStack S3
    s3_client = boto3.client('s3', endpoint_url='http://localhost:4566')
    
    try:
        s3_client.upload_file(
            Filename=str(output_path), 
            Bucket=bucket_name, 
            Key=output_path.name
        )
        print(f"Fichier correctement téléversé sur LocalStack S3 (Bucket: '{bucket_name}')")
    except Exception as e:
        print(f"Erreur lors du téléversement S3 : {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unpack and combine CSV files.")
    parser.add_argument("--input_dir", type=str, required=True)
    parser.add_argument("--output_file", type=str, required=True)
    parser.add_argument("--bucket_name", type=str, default="raw")
    args = parser.parse_args()

    unpack_data(args.input_dir, args.output_file)
