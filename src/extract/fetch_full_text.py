import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from scraper import build_session, get_page
from src.db.connection import get_connection

MAX_WORKERS = 10


def parse_full_text(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.select_one("div.post__content")
    if not content_div:
        return None

    for junk in content_div.select(".wp-block-file, .post-views"):
        junk.decompose()

    text = content_div.get_text(separator="\n", strip=True)
    return text if text else None


def fetch_one(session, doc_id, url):
    try:
        html = get_page(session, url)
        text = parse_full_text(html) if html else None
        return doc_id, text, None
    except Exception as e:
        return doc_id, None, str(e)


def main(limit=None, max_workers=MAX_WORKERS):
    conn = get_connection(as_dict=True)
    session = build_session()

    with conn.cursor() as cur:
        query = """
            SELECT documents.id, documents.detail_url
            FROM documents
            JOIN categories ON documents.category_id = categories.id
            WHERE categories.name = 'Решения'
              AND documents.detail_url IS NOT NULL
              AND documents.full_text_scraped_at IS NULL
            ORDER BY documents.id
        """
        if limit:
            query += f" LIMIT {int(limit)}"
        cur.execute(query)
        pending = cur.fetchall()

    print(f"{len(pending)} documents pending, {max_workers} concurrent workers, no delay")

    success_count = 0
    fail_count = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_one, session, row["id"], row["detail_url"]): row["id"]
            for row in pending
        }

        for future in as_completed(futures):
            doc_id, text, error = future.result()

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET full_text = %s, full_text_scraped_at = NOW() WHERE id = %s",
                    (text, doc_id)
                )
            conn.commit()

            if error:
                fail_count += 1
                print(f"  id={doc_id}: ERROR {error}")
            elif text:
                success_count += 1
            else:
                fail_count += 1
                print(f"  id={doc_id}: no content found")

    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s: {success_count} succeeded, {fail_count} failed")
    conn.close()


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else MAX_WORKERS
    main(limit=limit, max_workers=workers)