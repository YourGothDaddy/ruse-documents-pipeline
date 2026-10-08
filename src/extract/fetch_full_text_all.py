import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.extract.scraper import build_session, get_page
from src.extract.fetch_full_text import parse_full_text
from src.db.connection import get_connection

DEFAULT_CATEGORIES = ["Наредби", "Протоколи", "Предложения", "Приватизация"]
DEFAULT_WORKERS = 10


def fetch_one(session, doc_id, url):
    try:
        html = get_page(session, url)
        text = parse_full_text(html) if html else None
        return doc_id, text, None
    except Exception as e:
        return doc_id, None, str(e)


def main(categories, limit=None, max_workers=DEFAULT_WORKERS):
    conn = get_connection(as_dict=True)
    session = build_session()

    with conn.cursor() as cur:
        query = """
            SELECT d.id, d.detail_url
            FROM documents d
            JOIN categories c ON c.id = d.category_id
            WHERE c.name = ANY(%s)
              AND d.detail_url IS NOT NULL
              AND d.full_text_scraped_at IS NULL
            ORDER BY d.id
        """
        params = [categories]
        if limit:
            query += " LIMIT %s"
            params.append(limit)
        cur.execute(query, params)
        pending = cur.fetchall()

    print(f"{len(pending)} documents pending across {categories}, {max_workers} workers")

    ok = empty = failed = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_one, session, row["id"], row["detail_url"])
            for row in pending
        ]

        for future in as_completed(futures):
            doc_id, text, error = future.result()

            if error:
                # Leave full_text_scraped_at NULL so a rerun retries this document.
                failed += 1
                print(f"  id={doc_id}: ERROR {error}")
                continue

            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE documents
                    SET full_text = %s,
                        full_text_source = %s,
                        full_text_scraped_at = NOW()
                    WHERE id = %s
                    """,
                    (text, "detail_page" if text else None, doc_id),
                )
            conn.commit()

            if text:
                ok += 1
            else:
                empty += 1

    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s: {ok} with text, {empty} without content, {failed} errors")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch detail-page text for the given categories.")
    parser.add_argument("--categories", nargs="+", default=DEFAULT_CATEGORIES)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()
    main(args.categories, limit=args.limit, max_workers=args.workers)