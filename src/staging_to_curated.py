"""
Exercice 3 : Récupération depuis MySQL, tokenisation, insertion dans MongoDB (Curated).

Usage:
    python src/staging_to_curated.py \
        --db-host localhost --db-user root \
        --db-password root --db-name staging \
        --mongo-uri mongodb://localhost:27017/ \
        --tokenizer distilbert-base-uncased \
        --max-length 512
"""
import argparse
from datetime import datetime
import mysql.connector
from pymongo import MongoClient
from transformers import AutoTokenizer
from tqdm import tqdm


def get_staging_data(host, user, password, database, split="train"):
    """
    Récupère les textes depuis la table MySQL 'texts' pour un split donné.
    
    Args:
        host, user, password, database: paramètres de connexion MySQL
        split: nom du split à récupérer (défaut: "train")
    
    Returns:
        Liste de tuples (id, text) ou None en cas d'erreur.
    """
    # TODO:
    #   1. Créer une connexion MySQL
    #   2. Créer un curseur
    #   3. Exécuter : SELECT id, text FROM texts WHERE split = %s
    #      Indice : cursor.execute(query, (split,))
    #   4. Récupérer tous les résultats avec fetchall()
    #   5. Fermer la connexion
    #   6. Retourner les résultats
    pass


def tokenize_texts(texts, tokenizer, max_length=512):
    """
    Tokenise une liste de textes en mode batch.
    
    Args:
        texts: liste de chaînes de caractères
        tokenizer: tokenizer HuggingFace initialisé
        max_length: longueur maximale de tokenisation
    
    Returns:
        Liste de listes d'entiers (les input_ids de chaque texte).
    """
    # TODO:
    #   Appeler le tokenizer sur la liste complète de textes.
    #   Paramètres à utiliser :
    #     - truncation=True
    #     - max_length=max_length
    #     - padding=False   (pas besoin de padding pour du stockage)
    #   Retourner encoded["input_ids"]
    #
    #   Note : le tokenizer accepte directement une liste de textes,
    #   ce qui est beaucoup plus rapide qu'une boucle.
    pass


def prepare_documents(rows, all_tokens, split_name, tokenizer_name, max_length):
    """
    Prépare les documents à insérer dans MongoDB.
    
    Chaque document doit avoir la structure :
    {
        "original_id": <id MySQL>,
        "text": <texte original>,
        "tokens": <liste d'entiers>,
        "num_tokens": <nombre de tokens>,
        "metadata": {
            "source": "mysql_staging",
            "split": <split_name>,
            "tokenizer": <tokenizer_name>,
            "max_length": <max_length>,
            "processed_at": <timestamp ISO>
        }
    }
    
    Args:
        rows: liste de tuples (id, text) depuis MySQL
        all_tokens: liste de listes de tokens (même ordre que rows)
        split_name: nom du split
        tokenizer_name: nom du tokenizer utilisé
        max_length: longueur max de tokenisation
    
    Returns:
        Liste de dictionnaires prêts pour MongoDB.
    """
    # TODO:
    #   Parcourir rows et all_tokens en parallèle (zip ou index).
    #   Pour chaque paire, construire le dictionnaire décrit ci-dessus.
    #   Utiliser datetime.utcnow().isoformat() pour le timestamp.
    #   Retourner la liste de documents.
    pass


def insert_to_mongodb(documents, mongo_uri, batch_size=1000):
    """
    Insère les documents dans MongoDB par batches.
    
    Args:
        documents: liste de dictionnaires à insérer
        mongo_uri: URI de connexion MongoDB
        batch_size: taille des batches d'insertion
    """
    # TODO:
    #   1. Se connecter à MongoDB avec MongoClient(mongo_uri)
    #   2. Accéder à la base "curated", collection "wikitext"
    #   3. Supprimer les documents existants : collection.delete_many({})
    #   4. Insérer les documents par batch :
    #      - Parcourir documents par tranches de batch_size
    #        Indice : for i in range(0, len(documents), batch_size)
    #      - Appeler collection.insert_many(batch) sur chaque tranche
    #   5. Afficher le nombre total de documents insérés
    #   6. Fermer la connexion
    pass


def verify_mongodb(mongo_uri):
    """
    Vérifie les données insérées dans MongoDB.
    
    Affiche :
        - Nombre total de documents
        - 3 documents exemple (id, début du texte, nombre de tokens)
        - Statistiques sur le nombre de tokens (avg, min, max)
    """
    # TODO:
    #   1. Se connecter et accéder à la collection curated.wikitext
    #
    #   2. Nombre total : collection.count_documents({})
    #
    #   3. Aperçu : collection.find().limit(3)
    #      Afficher original_id, text[:60], num_tokens pour chaque doc
    #
    #   4. Statistiques via agrégation :
    #      pipeline = [
    #          {"$group": {
    #              "_id": None,
    #              "avg_tokens": {"$avg": "$num_tokens"},
    #              "min_tokens": {"$min": "$num_tokens"},
    #              "max_tokens": {"$max": "$num_tokens"}
    #          }}
    #      ]
    #      Exécuter avec collection.aggregate(pipeline)
    #
    #   5. Fermer la connexion
    pass


def main():
    parser = argparse.ArgumentParser(
        description="Staging (MySQL) vers Curated (MongoDB) avec tokenisation"
    )
    parser.add_argument("--db-host", type=str, default="localhost")
    parser.add_argument("--db-user", type=str, default="root")
    parser.add_argument("--db-password", type=str, default="root")
    parser.add_argument("--db-name", type=str, default="staging")
    parser.add_argument("--mongo-uri", type=str, default="mongodb://localhost:27017/")
    parser.add_argument("--tokenizer", type=str, default="distilbert-base-uncased")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--split", type=str, default="train")
    args = parser.parse_args()

    # 1. Récupérer les données depuis MySQL
    print(f"Récupération du split '{args.split}' depuis MySQL...")
    rows = get_staging_data(
        args.db_host, args.db_user, args.db_password,
        args.db_name, args.split
    )
    if not rows:
        print("Aucune donnée récupérée depuis MySQL.")
        return
    print(f"  {len(rows)} textes récupérés.")

    # 2. Initialiser le tokenizer
    print(f"Initialisation du tokenizer ({args.tokenizer})...")
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    # 3. Tokeniser les textes
    print("Tokenisation...")
    texts = [row[1] for row in rows]
    all_tokens = tokenize_texts(texts, tokenizer, args.max_length)
    print(f"  {len(all_tokens)} textes tokenisés.")

    # 4. Préparer les documents
    print("Préparation des documents...")
    documents = prepare_documents(
        rows, all_tokens, args.split, args.tokenizer, args.max_length
    )

    # 5. Insérer dans MongoDB
    print("Insertion dans MongoDB...")
    insert_to_mongodb(documents, args.mongo_uri)

    # 6. Vérification
    print("\n--- Vérification MongoDB ---")
    verify_mongodb(args.mongo_uri)

    print("\nTerminé.")


if __name__ == "__main__":
    main()