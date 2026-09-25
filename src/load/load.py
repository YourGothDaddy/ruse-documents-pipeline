import json
import glob
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_lookup_maps(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM categories")
        category_map = {name: id for id, name in cur.fetchall()}

        cur.execute("SELECT id, name FROM statuses")
        status_map = {name: id for id, name in cur.fetchall()}

    return category_map, status_map


def upsert_document(conn, doc, category_map, status_map):
    category_id = category_map.get(doc["category_name"])
    status_id = status_map.get(doc["status_name"])

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO documents (
                title, category_id, status_id, publish_date,
                file_url, file_type, file_size_kb, source_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_url, title) DO UPDATE SET
                category_id = EXCLUDED.category_id,
                status_id = EXCLUDED.status_id,
                publish_date = EXCLUDED.publish_date,
                file_url = EXCLUDED.file_url,
                file_type = EXCLUDED.file_type,
                file_size_kb = EXCLUDED.file_size_kb,
                scraped_at = NOW()
        """, (
            doc["title"], category_id, status_id, doc["publish_date"],
            doc["file_url"], doc["file_type"], doc["file_size_kb"], doc["source_url"]
        ))


def main():
    processed_files = sorted(glob.glob("data/processed/clean_*.json"))
    latest_file = processed_files[-1]

    print(f"Loading {latest_file}")

    with open(latest_file, encoding="utf-8") as f:
        documents = json.load(f)

    conn = get_connection()

    try:
        category_map, status_map = get_lookup_maps(conn)

        for doc in documents:
            upsert_document(conn, doc, category_map, status_map)

        conn.commit()
        print(f"Loaded {len(documents)} documents successfully")

    except Exception as e:
        conn.rollback()
        print(f"Error during load, rolled back: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()