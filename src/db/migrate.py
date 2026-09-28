import glob
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "sql", "migrations"
)


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
    )


def ensure_tracking_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()


def get_applied(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn, path):
    filename = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        sql = f.read()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)", (filename,)
            )
        conn.commit()
        print(f"Applied {filename}")
    except Exception as e:
        conn.rollback()
        print(f"Failed {filename}, rolled back: {e}")
        raise


def main():
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    conn = get_connection()

    try:
        ensure_tracking_table(conn)
        applied = get_applied(conn)
        pending = [p for p in files if os.path.basename(p) not in applied]

        if not pending:
            print("Database is up to date")
            return

        for path in pending:
            apply_migration(conn, path)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
