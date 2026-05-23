"""
Exercice 2 : Chargement de WikiText-2, nettoyage, insertion dans MySQL (Staging).

Usage:
    python src/load_to_staging.py \
        --db-host localhost --db-user root \
        --db-password root --db-name staging
"""
import argparse
from datasets import load_dataset
import mysql.connector
from mysql.connector import Error


def download_wikitext():
    """
    Charge le dataset WikiText-2 depuis HuggingFace.
    
    Retourne l'objet dataset contenant les splits 'train', 'validation', 'test'.
    Chaque élément possède un champ 'text'.
    """

    from datasets import load_dataset

    dataset = load_dataset("Salesforce/wikitext", name="wikitext-2-raw-v1") 
    return dataset


def clean_split(dataset_split):
    """
    Nettoie un split du dataset.
    
    Args:
        dataset_split: un split HuggingFace (ex: dataset["train"])
    
    Returns:
        Liste de chaînes de caractères nettoyées.
    """
    texts = [entry["text"] for entry in dataset_split]
    cleaned = set()
    for text in texts : #""" set permet de supprimer les doublons """
        if text.strip() != "":
            cleaned.add(text)
    return list(cleaned)
    

def create_mysql_connection(host, user, password, database):
    """
    Crée et retourne une connexion MySQL.
    Retourne None en cas d'erreur.
    """
    try : 
        conn = mysql.connector.connect(
            host=host, user=user, port=3307,
            password=password, database=database
        )
        print("Connexion MySQL réussie.")
        return conn
    except Error as e:
        print(f"Erreur de connexion MySQL : {e}")
        return None

def create_table(connection):
    """
    Crée la table 'texts' dans la base staging si elle n'existe pas.
    
    Schéma attendu :
        id          INT AUTO_INCREMENT PRIMARY KEY
        text        TEXT NOT NULL
        split       VARCHAR(20) NOT NULL
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    """
    connection.cursor().execute("""
        CREATE TABLE IF NOT EXISTS texts (id INT AUTO_INCREMENT PRIMARY KEY, 
                                          text TEXT NOT NULL, 
                                          split VARCHAR(20) NOT NULL, 
                                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) 
                                          """ ) 
    connection.commit() 


def insert_data(connection, texts, split_name):
    """
    Insère les textes nettoyés dans la table 'texts'.
    
    Args:
        connection: connexion MySQL active
        texts: liste de chaînes de caractères
        split_name: nom du split ("train", "validation", "test")
    """
    cursor = connection.cursor()
    values = list()
    for text in texts :
        values.append((text, split_name))
    cursor.executemany("INSERT INTO texts (text, split) VALUES (%s, %s)", values)
    connection.commit()
    print(f"  {cursor.rowcount} lignes insérées.")


def validate_data(connection):
    """
    Valide les données insérées en exécutant des requêtes SQL.
    
    Requêtes à exécuter :
        1. Nombre de lignes par split (GROUP BY)
        2. Nombre de textes vides (WHERE TRIM(text) = '')
        3. Aperçu des 5 premières lignes (id, début du texte, split)
    """
    cursor = connection.cursor()

    print("\n  1. Nombre de lignes par split :")
    cursor.execute("SELECT split, COUNT(*) FROM texts GROUP BY split")
    for row in cursor.fetchall():
        print(f"    - Split '{row[0]}': {row[1]} lignes")

    print("\n  2. Nombre de textes vides (après TRIM) :")
    cursor.execute("SELECT COUNT(*) FROM texts WHERE TRIM(text) = ''")
    empty_count = cursor.fetchone()[0]
    print(f"    - {empty_count} textes vides")

    print("\n  3. Aperçu des 5 premières lignes :")
    cursor.execute("SELECT id, LEFT(text, 80) as text_preview, split FROM texts LIMIT 5")
    for row in cursor.fetchall():
        print(f"    - ID: {row[0]}, Texte: '{row[1]}...', Split: '{row[2]}'")

    cursor.close()






def main():
    parser = argparse.ArgumentParser(
        description="Charge WikiText-2 dans MySQL (zone Staging)"
    )
    parser.add_argument("--db-host", type=str, default="localhost")
    parser.add_argument("--db-user", type=str, default="root")
    parser.add_argument("--db-password", type=str, default="root")
    parser.add_argument("--db-name", type=str, default="staging")
    args = parser.parse_args()

    # 1. Charger le dataset
    print("Chargement du dataset WikiText-2...")
    dataset = download_wikitext()
    if dataset is None:
        print("Erreur lors du chargement du dataset.")
        return

    # 2. Connexion MySQL
    print("Connexion à MySQL...")
    connection = create_mysql_connection(
        args.db_host, args.db_user, args.db_password, args.db_name
    )
    if connection is None:
        return

    # 3. Créer la table
    print("Création de la table...")
    create_table(connection)

    # 4. Nettoyer et insérer chaque split
    for split_name in ["train", "validation", "test"]:
        print(f"\nTraitement du split '{split_name}'...")
        cleaned = clean_split(dataset[split_name])
        print(f"  {len(cleaned)} lignes après nettoyage")
        insert_data(connection, cleaned, split_name)

    # 5. Validation
    print("\n--- Validation des données ---")
    validate_data(connection)

    # 6. Fermeture
    connection.close()
    print("\nTerminé.")


if __name__ == "__main__":
    main()