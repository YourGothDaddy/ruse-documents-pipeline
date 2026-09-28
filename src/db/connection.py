import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
    )


def get_known_detail_urls():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT detail_url FROM documents WHERE detail_url IS NOT NULL")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()
