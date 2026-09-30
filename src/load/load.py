import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from src.db.run_log import start_run, finish_run, fail_run
from src.db.connection import get_connection

def get_lookup_maps(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM categories")
        category_map = {row["name"]: row["id"] for row in cur.fetchall()}

        cur.execute("SELECT id, name FROM statuses")
        status_map = {row["name"]: row["id"] for row in cur.fetchall()}

        cur.execute("SELECT id, name FROM topics")
        topic_map = {row["name"]: row["id"] for row in cur.fetchall()}

    return category_map, status_map, topic_map

def upsert_document(conn, doc, category_map, status_map, topic_map):
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
            RETURNING id
        """, (
            doc["title"], category_id, status_id, doc["publish_date"],
            doc["file_url"], doc["file_type"], doc["file_size_kb"], doc["source_url"],
            doc["detail_url"], doc.get("description"),
            doc.get("decision_number"), doc.get("protocol_number"),
            doc.get("regulation_number"), doc.get("session_date")
        ))
        document_id = cur.fetchone()["id"]

        cur.execute("DELETE FROM document_topics WHERE document_id = %s", (document_id,))
        for topic_name in doc.get("topics", []):
            topic_id = topic_map.get(topic_name)
            if topic_id:
                cur.execute(
                    "INSERT INTO document_topics (document_id, topic_id) VALUES (%s, %s)",
                    (document_id, topic_id)
                )

        cur.execute("DELETE FROM document_law_references WHERE document_id = %s", (document_id,))
        for law_code in doc.get("law_references", []):
            cur.execute(
                "INSERT INTO document_law_references (document_id, law_code) VALUES (%s, %s)",
                (document_id, law_code)
            )
            
def main(input_path=None):
    if input_path is None:
        processed_files = sorted(glob.glob("data/processed/clean_*.json"))
        input_path = processed_files[-1]

    print(f"Loading {input_path}")

    with open(input_path, encoding="utf-8") as f:
        documents = json.load(f)

    conn = get_connection(as_dict=True)
    run_id = start_run(conn)

    try:
        category_map, status_map, topic_map = get_lookup_maps(conn)

        new_count = 0
        for doc in documents:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM documents WHERE detail_url = %s", (doc["detail_url"],)
                )
                is_new = cur.fetchone() is None
            if is_new:
                new_count += 1
            upsert_document(conn, doc, category_map, status_map, topic_map)

        conn.commit()
        finish_run(conn, run_id, len(documents), new_count)
        print(f"Loaded {len(documents)} documents successfully, {new_count} new")

    except Exception as e:
        conn.rollback()
        fail_run(conn, run_id, e)
        print(f"Error during load, rolled back: {e}")
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    main()