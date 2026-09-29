import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from src.db.connection import get_connection


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
                file_url, file_type, file_size_kb, source_url,
                detail_url, description,
                decision_number, protocol_number, regulation_number, session_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (detail_url) DO UPDATE SET
                title = EXCLUDED.title,
                category_id = EXCLUDED.category_id,
                status_id = EXCLUDED.status_id,
                publish_date = EXCLUDED.publish_date,
                file_url = EXCLUDED.file_url,
                file_type = EXCLUDED.file_type,
                file_size_kb = EXCLUDED.file_size_kb,
                source_url = EXCLUDED.source_url,
                description = EXCLUDED.description,
                decision_number = EXCLUDED.decision_number,
                protocol_number = EXCLUDED.protocol_number,
                regulation_number = EXCLUDED.regulation_number,
                session_date = EXCLUDED.session_date,
                scraped_at = NOW()
        """, (
            doc["title"], category_id, status_id, doc["publish_date"],
            doc["file_url"], doc["file_type"], doc["file_size_kb"], doc["source_url"],
            doc["detail_url"], doc.get("description"),
            doc.get("decision_number"), doc.get("protocol_number"),
            doc.get("regulation_number"), doc.get("session_date")
        ))

def main(input_path=None):
    if input_path is None:
        processed_files = sorted(glob.glob("data/processed/clean_*.json"))
        input_path = processed_files[-1]

    print(f"Loading {input_path}")

    with open(input_path, encoding="utf-8") as f:
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