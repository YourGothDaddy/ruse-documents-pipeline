from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, timedelta

from db import get_connection

app = FastAPI(title="Ruse Documents API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stats")
def get_stats():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM documents")
        total = cur.fetchone()["total"]

        thirty_days_ago = date.today() - timedelta(days=30)
        cur.execute(
            "SELECT COUNT(*) AS recent FROM documents WHERE publish_date >= %s",
            (thirty_days_ago,)
        )
        recent = cur.fetchone()["recent"]

        cur.execute("""
            SELECT categories.name, COUNT(*) AS count
            FROM documents
            JOIN categories ON documents.category_id = categories.id
            GROUP BY categories.name
            ORDER BY count DESC
        """)
        by_category = cur.fetchall()

        cur.execute("""
            SELECT statuses.name, COUNT(*) AS count
            FROM documents
            JOIN statuses ON documents.status_id = statuses.id
            GROUP BY statuses.name
        """)
        by_status = cur.fetchall()

    conn.close()

    return {
        "total_documents": total,
        "documents_last_30_days": recent,
        "by_category": by_category,
        "by_status": by_status,
    }


@app.get("/api/documents")
def get_documents(category: str = None, status: str = None, search: str = None, limit: int = 50):
    conn = get_connection()

    query = """
        SELECT documents.id, documents.title, categories.name AS category,
               statuses.name AS status, documents.publish_date,
               documents.file_url, documents.file_type
        FROM documents
        JOIN categories ON documents.category_id = categories.id
        JOIN statuses ON documents.status_id = statuses.id
        WHERE 1=1
    """
    params = []

    if category:
        query += " AND categories.name = %s"
        params.append(category)

    if status:
        query += " AND statuses.name = %s"
        params.append(status)

    if search:
        query += " AND documents.title ILIKE %s"
        params.append(f"%{search}%")

    query += " ORDER BY documents.publish_date DESC LIMIT %s"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(query, params)
        results = cur.fetchall()

    conn.close()
    return results


@app.get("/api/documents/{document_id}")
def get_document(document_id: int):
    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT documents.*, categories.name AS category, statuses.name AS status
            FROM documents
            JOIN categories ON documents.category_id = categories.id
            JOIN statuses ON documents.status_id = statuses.id
            WHERE documents.id = %s
        """, (document_id,))
        result = cur.fetchone()

    conn.close()

    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return result
