import argparse
from pathlib import Path
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

def preprocess_data(data_file: str, output_dir: str) -> None:
    """
    Preprocess raw protein sequence data for model training.

    This function loads the raw data, cleans it, encodes labels, and splits
    it into train/validation/test sets. The split strategy must handle the
    extreme class imbalance in the Pfam dataset.
    """
    data_path = Path(data_file)
    output_path = Path(output_dir)
    
    # Création du dossier de sortie s'il n'existe pas
    output_path.mkdir(parents=True, exist_ok=True)

    print("1. Chargement des données...")
    df = pd.read_csv(data_path)

    print("2. Suppression des valeurs manquantes...")
    df = df.dropna()

    print("3. Encodage de la colonne 'family_accession'...")
    le = LabelEncoder()
    # On crée une nouvelle colonne encodée (ou on écrase l'ancienne)
    df['family_accession_encoded'] = le.fit_transform(df['family_accession'])

    print("4. Séparation des données (Split strategy)...")
    # On compte le nombre d'occurrences pour chaque famille
    class_counts = df['family_accession_encoded'].value_counts()

    # Pour faire un split train/val/test, il nous faut au minimum 3 échantillons par classe.
    # Les classes ayant moins de 3 échantillons seront considérées comme "rares".
    rare_classes = class_counts[class_counts < 3].index

    # On sépare le dataset en deux : les classes fréquentes et les classes rares
    df_rare = df[df['family_accession_encoded'].isin(rare_classes)]
    df_freq = df[~df['family_accession_encoded'].isin(rare_classes)]

    # Split stratifié sur les classes fréquentes (80% Train, 20% Temp)
    train_freq, temp_freq = train_test_split(
        df_freq, 
        test_size=0.2, 
        stratify=df_freq['family_accession_encoded'], 
        random_state=42
    )

    # Split stratifié de 'Temp' en Validation et Test (50% de 20% = 10% Test, 10% Val)
    val_df, test_df = train_test_split(
        temp_freq, 
        test_size=0.5, 
        stratify=temp_freq['family_accession_encoded'], 
        random_state=42
    )

    # On ajoute les classes rares exclusivement au jeu d'entraînement
    train_df = pd.concat([train_freq, df_rare], ignore_index=True)

    # On mélange le jeu d'entraînement pour éviter que toutes les classes rares soient à la fin
    train_df = train_df.sample(frac=1, random_state=42).reset_index(drop=True)

    print("5. Sauvegarde des fichiers dans la zone Staging (Silver)...")
    train_df.to_csv(output_path / "train.csv", index=False)
    val_df.to_csv(output_path / "val.csv", index=False)
    test_df.to_csv(output_path / "test.csv", index=False)

    print(f"Terminé ! Taille des sets - Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess Pfam data.")
    parser.add_argument("--data_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)

    args = parser.parse_args()

    preprocess_data(args.data_file, args.output_dir)