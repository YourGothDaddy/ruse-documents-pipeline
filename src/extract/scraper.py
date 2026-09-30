import json
import os
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CATEGORY_URL = "https://obs.ruse-bg.eu/document-category/{slug}/page/{page}/"
RESHENIA_URL = "https://obs.ruse-bg.eu/category/решения/"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
REQUEST_TIMEOUT = (10, 30)
REQUEST_DELAY_SECONDS = 0.5
MAX_PAGES = 1000
KNOWN_PAGES_TO_STOP = 2


def build_session():
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session = requests.Session()
    session.headers.update(HEADERS)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_page(session, url):
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text


def parse_documents(html, category_key, source_url):
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    for article in soup.find_all("article", class_="lsvr_document"):
        title_tag = article.select_one("h2.post__title a.post__title-link")
        if not title_tag:
            continue

        attachment_link = article.select_one("a.post__attachment-link")
        extension_tag = article.select_one("span.post__attachment-extension")
        filesize_tag = article.select_one("span.post__attachment-filesize")
        date_tag = article.select_one("span.post__meta-date")

        file_type = None
        if extension_tag:
            file_type = (
                extension_tag.get_text(strip=True)
                .replace("File extension:", "")
                .strip()
                .lower()
            )

        documents.append({
            "title": title_tag.get_text(strip=True),
            "detail_url": title_tag.get("href"),
            "file_url": attachment_link.get("href") if attachment_link else None,
            "file_type": file_type,
            "file_size_raw": filesize_tag.get_text(strip=True) if filesize_tag else None,
            "category": category_key,
            "publish_date_raw": date_tag.get_text(strip=True) if date_tag else None,
            "source_url": source_url,
        })

    return documents


def parse_reshenia_jsonld(html, source_url):
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(data, dict) or "hasPart" not in data:
            continue

        for item in data["hasPart"]:
            if item.get("@type") != "BlogPosting":
                continue

            date_published = item.get("datePublished")

            documents.append({
                "title": item.get("headline"),
                "detail_url": item.get("url"),
                "file_url": None,
                "file_type": None,
                "file_size_raw": None,
                "category": "reshenia",
                "publish_date_raw": date_published.split("T")[0] if date_published else None,
                "source_url": source_url,
                "description": item.get("description"),
            })

    return documents


def scrape_pages(session, url_for_page, parse_page, label, known_urls=None):
    documents = []
    consecutive_known = 0

    for page in range(1, MAX_PAGES + 1):
        url = url_for_page(page)
        print(f"Scraping {label} page {page}...")
        html = get_page(session, url)

        if html is None:
            print(f"Reached the end of {label} at page {page}")
            break

        page_documents = parse_page(html, url)

        if not page_documents:
            if page == 1:
                raise RuntimeError(f"No documents found on page 1 of {label}, site structure may have changed")
            print(f"No documents on {label} page {page}, stopping")
            break

        documents.extend(page_documents)

        if known_urls is not None:
            if all(doc["detail_url"] in known_urls for doc in page_documents):
                consecutive_known += 1
                if consecutive_known >= KNOWN_PAGES_TO_STOP:
                    print(f"{label}: {KNOWN_PAGES_TO_STOP} consecutive pages already known, stopping at page {page}")
                    break
            else:
                consecutive_known = 0

        time.sleep(REQUEST_DELAY_SECONDS)

    return documents


def scrape_category(session, slug, key):
    return scrape_pages(
        session,
        lambda page: CATEGORY_URL.format(slug=slug, page=page),
        lambda html, url: parse_documents(html, key, url),
        key,
    )


def scrape_reshenia(session, known_urls=None):
    return scrape_pages(
        session,
        lambda page: RESHENIA_URL if page == 1 else f"{RESHENIA_URL}page/{page}/",
        parse_reshenia_jsonld,
        "reshenia",
        known_urls,
    )


def main(known_urls=None):
    session = build_session()
    results = []

    results.extend(scrape_category(session, "наредби", "naredbi"))
    results.extend(scrape_category(session, "протоколи", "protokoli"))
    results.extend(scrape_category(session, "предложения", "predlojenia"))
    results.extend(scrape_category(session, "приватизация", "privatizacia"))
    results.extend(scrape_reshenia(session, known_urls))

    if not results:
        raise RuntimeError("Scrape returned no documents")

    if known_urls is not None:
        new_count = sum(1 for doc in results if doc["detail_url"] not in known_urls)
        print(f"{new_count} of {len(results)} scraped documents are new")

    os.makedirs("data/raw", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"data/raw/scrape_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(results)} documents to {output_path}")
    return output_path


if __name__ == "__main__":
    import sys

    if "incremental" in sys.argv[1:]:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from db.connection import get_known_detail_urls

        main(known_urls=get_known_detail_urls())
    else:
        main()
