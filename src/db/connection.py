import os

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_connection(as_dict=False):
    kwargs = {
        "host": os.getenv("DB_HOST"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "sslmode": os.getenv("DB_SSLMODE", "prefer"),
    }
    if as_dict:
        kwargs["cursor_factory"] = RealDictCursor
    return psycopg2.connect(**kwargs)


def get_known_detail_urls():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT detail_url FROM documents WHERE detail_url IS NOT NULL")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()