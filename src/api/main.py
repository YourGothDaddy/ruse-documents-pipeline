from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, timedelta

from src.api.db import get_connection

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

        cur.execute("""
            SELECT EXTRACT(YEAR FROM publish_date) AS year, COUNT(*) AS count
            FROM documents
            WHERE publish_date IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
        """)
        by_year = cur.fetchall()

        cur.execute("""
            SELECT COALESCE(file_type, 'none') AS file_type, COUNT(*) AS count
            FROM documents
            GROUP BY file_type
            ORDER BY count DESC
        """)
        by_file_type = cur.fetchall()

    conn.close()

    return {
        "total_documents": total,
        "documents_last_30_days": recent,
        "by_category": by_category,
        "by_status": by_status,
        "by_year": by_year,
        "by_file_type": by_file_type,
    }

@app.get("/api/trends/category-volume")
def get_category_volume():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXTRACT(YEAR FROM documents.publish_date)::int AS year,
                   categories.name AS category,
                   COUNT(*) AS count
            FROM documents
            JOIN categories ON documents.category_id = categories.id
            WHERE documents.publish_date IS NOT NULL
            GROUP BY year, categories.name
            ORDER BY year
        """)
        rows = cur.fetchall()

        cur.execute("SELECT COUNT(*) AS missing FROM documents WHERE publish_date IS NULL")
        missing_date_count = cur.fetchone()["missing"]
    conn.close()

    years = sorted({row["year"] for row in rows})
    by_category = {}
    for row in rows:
        by_category.setdefault(row["category"], {y: 0 for y in years})
        by_category[row["category"]][row["year"]] = row["count"]

    return {
        "years": years,
        "categories": {cat: [counts[y] for y in years] for cat, counts in by_category.items()},
        "excluded_missing_date": missing_date_count,
    }

@app.get("/api/trends/repeal-rate")
def get_repeal_rate():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXTRACT(YEAR FROM documents.publish_date)::int AS year,
                   COUNT(*) FILTER (WHERE statuses.name = 'repealed') AS repealed,
                   COUNT(*) AS total
            FROM documents
            JOIN statuses ON documents.status_id = statuses.id
            WHERE documents.publish_date IS NOT NULL
            GROUP BY year
            ORDER BY year
        """)
        rows = cur.fetchall()
    conn.close()

    return {
        "years": [row["year"] for row in rows],
        "repealed": [row["repealed"] for row in rows],
        "total": [row["total"] for row in rows],
        "repeal_rate_percent": [
            round((row["repealed"] / row["total"]) * 100, 1) if row["total"] else 0
            for row in rows
        ],
    }

@app.get("/api/documents")
def get_documents(
    category: str = None,
    status: str = None,
    search: str = None,
    file_type: str = None,
    has_file: bool = None,
    date_from: str = None,
    date_to: str = None,
    topic: str = None,
    sort_by: str = "publish_date",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0
):
    conn = get_connection()

    base_query = """
        FROM documents
        JOIN categories ON documents.category_id = categories.id
        JOIN statuses ON documents.status_id = statuses.id
        WHERE 1=1
    """
    params = []

    if category:
        base_query += " AND categories.name = %s"
        params.append(category)

    if status:
        base_query += " AND statuses.name = %s"
        params.append(status)

    if search:
        base_query += " AND (documents.title ILIKE %s OR documents.search_vector @@ plainto_tsquery('simple', %s))"
        params.append(f"%{search}%")
        params.append(search)

    if file_type:
        base_query += " AND documents.file_type = %s"
        params.append(file_type)

    if has_file is not None:
        base_query += " AND documents.file_url IS NOT NULL" if has_file else " AND documents.file_url IS NULL"

    if date_from:
        base_query += " AND documents.publish_date >= %s"
        params.append(date_from)

    if date_to:
        base_query += " AND documents.publish_date <= %s"
        params.append(date_to)

    if topic:
        base_query += """
            AND documents.id IN (
                SELECT document_id FROM document_topics
                JOIN topics ON document_topics.topic_id = topics.id
                WHERE topics.name = %s
            )
        """
        params.append(topic)

    allowed_sort_columns = {
        "publish_date": "documents.publish_date",
        "title": "documents.title",
        "category": "categories.name",
        "number": "COALESCE(documents.decision_number, documents.regulation_number, documents.protocol_number)",
    }
    sort_column = allowed_sort_columns.get(sort_by, "documents.publish_date")
    sort_direction = "ASC" if sort_order == "asc" else "DESC"

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total {base_query}", params)
        total_count = cur.fetchone()["total"]

        tiebreaker = (
            f", documents.decision_number {sort_direction} NULLS LAST"
            if sort_by == "publish_date"
            else ""
        )

        select_query = f"""
            SELECT documents.id, documents.title, categories.name AS category,
                   statuses.name AS status, documents.publish_date,
                   documents.file_url, documents.file_type, documents.detail_url,
                   documents.decision_number, documents.regulation_number, documents.protocol_number
            {base_query}
            ORDER BY {sort_column} {sort_direction} NULLS LAST{tiebreaker}
            LIMIT %s OFFSET %s
        """
        cur.execute(select_query, params + [limit, offset])
        results = cur.fetchall()

    conn.close()
    return {"total": total_count, "limit": limit, "offset": offset, "documents": results}

@app.get("/api/documents/sources")
def get_document_sources():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                CASE
                    WHEN source_url LIKE '%archiveobs.ruse-bg.eu%' THEN 'archive'
                    WHEN source_url LIKE '%/news/%' THEN 'news_backfill'
                    ELSE 'main_site'
                END AS source,
                COUNT(*) AS count
            FROM documents
            GROUP BY source
            ORDER BY count DESC
        """)
        rows = cur.fetchall()
    conn.close()
    return {"sources": rows}

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

@app.get("/api/quality")
def get_quality():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, started_at, finished_at, status, documents_processed, documents_new, error_message
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT 1
        """)
        last_run = cur.fetchone()

        cur.execute("SELECT COUNT(*) AS total FROM documents")
        total = cur.fetchone()["total"]

        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE decision_number IS NOT NULL) AS parsed, COUNT(*) AS total
            FROM documents WHERE category_id = (SELECT id FROM categories WHERE name = 'Решения')
        """)
        reshenia_parse = cur.fetchone()

        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE regulation_number IS NOT NULL) AS parsed, COUNT(*) AS total
            FROM documents WHERE category_id = (SELECT id FROM categories WHERE name = 'Наредби')
        """)
        naredbi_parse = cur.fetchone()

        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE protocol_number IS NOT NULL) AS parsed, COUNT(*) AS total
            FROM documents WHERE category_id = (SELECT id FROM categories WHERE name = 'Протоколи')
        """)
        protokoli_parse = cur.fetchone()

        cur.execute("SELECT COUNT(*) AS missing FROM documents WHERE publish_date IS NULL")
        missing_dates = cur.fetchone()["missing"]

        cur.execute("SELECT COUNT(*) AS missing FROM documents WHERE file_url IS NULL")
        no_file = cur.fetchone()["missing"]

        cur.execute("SELECT COUNT(DISTINCT document_id) AS tagged FROM document_topics")
        topics_tagged = cur.fetchone()["tagged"]

    conn.close()

    return {
        "last_run": last_run,
        "total_documents": total,
        "field_parse_rates": {
            "reshenia_decision_number": reshenia_parse,
            "naredbi_regulation_number": naredbi_parse,
            "protokoli_protocol_number": protokoli_parse,
        },
        "missing_publish_date": missing_dates,
        "documents_without_file": no_file,
        "documents_with_topics": topics_tagged,
    }

@app.get("/api/topics")
def get_topics():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM topics ORDER BY name")
        topics = cur.fetchall()
    conn.close()
    return topics

@app.get("/api/topics/distribution")
def get_topic_distribution():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT topics.name, COUNT(*) AS count
            FROM document_topics
            JOIN topics ON document_topics.topic_id = topics.id
            GROUP BY topics.name
            ORDER BY count DESC
        """)
        rows = cur.fetchall()
    conn.close()
    return {"topics": rows}

@app.get("/api/topics/trend")
def get_topic_trend():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXTRACT(YEAR FROM documents.publish_date)::int AS year,
                   topics.name AS topic,
                   COUNT(*) AS count
            FROM document_topics
            JOIN topics ON document_topics.topic_id = topics.id
            JOIN documents ON document_topics.document_id = documents.id
            WHERE documents.publish_date IS NOT NULL
            GROUP BY year, topic
            ORDER BY year
        """)
        rows = cur.fetchall()
    conn.close()

    years = sorted({row["year"] for row in rows})
    by_topic = {}
    for row in rows:
        by_topic.setdefault(row["topic"], {y: 0 for y in years})
        by_topic[row["topic"]][row["year"]] = row["count"]

    return {
        "years": years,
        "topics": {topic: [counts[y] for y in years] for topic, counts in by_topic.items()},
    }

@app.get("/api/law-references/distribution")
def get_law_reference_distribution():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT law_code, COUNT(*) AS count
            FROM document_law_references
            GROUP BY law_code
            ORDER BY count DESC
            LIMIT 15
        """)
        rows = cur.fetchall()
    conn.close()
    return {"law_references": rows}

@app.get("/api/tax-rates")
def get_tax_rates():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT tax_type, rate, rate_unit, source_document, last_checked FROM tax_rates")
        rows = cur.fetchall()
    conn.close()
    return {"tax_rates": rows}