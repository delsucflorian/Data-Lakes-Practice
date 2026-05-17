import argparse
from pathlib import Path
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle


def preprocess_data(data_file: str, output_dir: str) -> None:
    data_path = Path(data_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Chargement des données
    df = pd.read_csv(data_path)

    # 2. Nettoyage
    df = df.dropna()

    # 3. Encodage des labels
    le = LabelEncoder()
    df['family_accession_encoded'] = le.fit_transform(df['family_accession'])

    # 4. Stratégie de fractionnement
    class_counts = df['family_accession_encoded'].value_counts()
    
    classes_1 = class_counts[class_counts == 1].index
    classes_2 = class_counts[class_counts == 2].index
    classes_3_plus = class_counts[class_counts >= 3].index
    
    # 4a. Classes avec 1 élément -> 100% Train
    train_1 = df[df['family_accession_encoded'].isin(classes_1)]
    
    # 4b. Classes avec 2 éléments -> 1 Train, 1 Test
    df_2 = df[df['family_accession_encoded'].isin(classes_2)]
    train_2 = df_2.groupby('family_accession_encoded').head(1)
    test_2 = df_2.groupby('family_accession_encoded').tail(1)
    
    # 4c. Classes avec 3 éléments ou plus -> Fractionnement 70/15/15
    df_3_plus = df[df['family_accession_encoded'].isin(classes_3_plus)]
    
    train_3, temp_3 = train_test_split(
        df_3_plus, 
        test_size=0.30, 
        stratify=df_3_plus['family_accession_encoded'], 
        random_state=42
    )
    
    val_3, test_3 = train_test_split(
        temp_3, 
        test_size=0.50, 
        stratify=temp_3['family_accession_encoded'], 
        random_state=42
    )
    
    # Concaténation et mélange (shuffle) pour distribution aléatoire
    train_final = shuffle(pd.concat([train_1, train_2, train_3], axis=0), random_state=42)
    val_final = shuffle(val_3, random_state=42)
    test_final = shuffle(pd.concat([test_2, test_3], axis=0), random_state=42)

    # 5. Sauvegarde
    train_final.to_csv(output_path / "train.csv", index=False)
    val_final.to_csv(output_path / "val.csv", index=False)
    test_final.to_csv(output_path / "test.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess Pfam data.")
    parser.add_argument("--data_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)

    args = parser.parse_args()

    preprocess_data(args.data_file, args.output_dir)
