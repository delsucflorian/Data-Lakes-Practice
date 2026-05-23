"""
Exercice 1 : Test des connexions MySQL et MongoDB.
Exécutez ce script après avoir lancé docker-compose up -d
et attendu ~30s que MySQL s'initialise.
"""
import mysql.connector
import pymongo


def test_mysql():
    print("Test de connexion MySQL...")
    try:
        conn = mysql.connector.connect(
            host="localhost", user="root",
            password="root", database="staging"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"  MySQL OK : {result}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  MySQL ERREUR : {e}")
        return False


def test_mongodb():
    print("Test de connexion MongoDB...")
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017/",
                                     serverSelectionTimeoutMS=3000)
        client.server_info()  # Force la connexion
        db = client["test"]
        db["ping"].insert_one({"status": "ok"})
        result = db["ping"].find_one()
        print(f"  MongoDB OK : {result}")
        db["ping"].drop()
        client.close()
        return True
    except Exception as e:
        print(f"  MongoDB ERREUR : {e}")
        return False


if __name__ == "__main__":
    mysql_ok = test_mysql()
    mongo_ok = test_mongodb()

    print("\n--- Résumé ---")
    print(f"MySQL :  {'✓' if mysql_ok else '✗'}")
    print(f"MongoDB: {'✓' if mongo_ok else '✗'}")

    if mysql_ok and mongo_ok:
        print("\nTout est prêt, vous pouvez passer à l'exercice 2 !")
    else:
        print("\nCorrigez les erreurs avant de continuer.")