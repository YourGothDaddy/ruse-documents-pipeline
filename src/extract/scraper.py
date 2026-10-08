import json
import os
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import unquote
import re

CATEGORY_URL = "https://obs.ruse-bg.eu/document-category/{slug}/page/{page}/"
RESHENIA_URL = "https://obs.ruse-bg.eu/category/решения/"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
REQUEST_TIMEOUT = (10, 30)
REQUEST_DELAY_SECONDS = 0.5
MAX_PAGES = 2000
KNOWN_PAGES_TO_STOP = 2

NEWS_URL = "https://obs.ruse-bg.eu/news/page/{page}/"

RESHENIA_CATEGORY_SLUGS = {
    "решения",
    "решения-от-мандат-2011-2015-г",
    "решения-от-миналия-мандат",
}

ARCHIVE_TYPE_MAP = {
    "1002": "protokoli",           # Протокол
    "1003": "protokoli",           # Протокол от заседание на ОС
    "1004": "protokoli_komisii",   # Протокол от заседание на комисия
    "1005": "reshenia",            # Решение на ОС
    "1006": "reshenia_komisii",    # Решение на комисия
    "1007": "otgovori",            # Отговор
    "1008": "pisma",               # Писмо
    "1009": "dneven_red",          # Дневен ред
    "1010": "predlojenia",         # Предложение
    "1011": "proektonaredbi",      # Проекто наредба
    "1012": "naredbi",             # Наредба
    "1013": "prilojenia",          # Приложение
    "1014": "drugi",               # Друго
}

CATEGORY_NAME_MAP = {
    "protokoli": "Протоколи",
    "protokoli_komisii": "Протоколи от комисии",
    "reshenia": "Решения",
    "reshenia_komisii": "Решения на комисии",
    "otgovori": "Отговори",
    "pisma": "Писма",
    "dneven_red": "Дневен ред",
    "predlojenia": "Предложения",
    "proektonaredbi": "Проекто наредби",
    "naredbi": "Наредби",
    "prilojenia": "Приложения",
    "drugi": "Други",
}

ARCHIVE_URL = "https://archiveobs.ruse-bg.eu/"
ARCHIVE_YEARS = range(2019, 2027)

ARCHIVE_TYPE_MAP = {
    "1002": "protokoli",
    "1003": "protokoli",
    "1004": "protokoli_komisii",
    "1005": "reshenia",
    "1006": "reshenia_komisii",
    "1007": "otgovori",
    "1008": "pisma",
    "1009": "dneven_red",
    "1010": "predlojenia",
    "1011": "proektonaredbi",
    "1012": "naredbi",
    "1013": "prilojenia",
    "1014": "drugi",
}

RESULT_TITLE_PATTERN = re.compile(
    r"Наименование\s*:\s*<span>([^<]+)</span>", re.IGNORECASE
)
RESULT_ND_PATTERN = re.compile(
    r"номер\s*/\s*дата\s*:\s*<span>([^<]+)</span>", re.IGNORECASE
)
RESULT_PDF_PATTERN = re.compile(
    r'href="(https://archive\.ruse-bg\.eu/\?df=[^"]+)"'
)


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

def parse_news_feed(html, source_url):
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    for article in soup.find_all("article"):
        term_link = article.select_one("a.post__term-link")
        if not term_link:
            continue

        href = term_link.get("href", "")
        category_slug = unquote(href.rstrip("/").split("/")[-1])
        if category_slug not in RESHENIA_CATEGORY_SLUGS:
            continue

        title_tag = article.select_one("h2.post__title a.post__title-link")
        if not title_tag:
            continue

        date_tag = article.select_one("span.post__meta-date")

        documents.append({
            "title": title_tag.get_text(strip=True),
            "detail_url": title_tag.get("href"),
            "file_url": None,
            "file_type": None,
            "file_size_raw": None,
            "category": "reshenia",
            "publish_date_raw": date_tag.get_text(strip=True) if date_tag else None,
            "source_url": source_url,
        })

    return documents


def scrape_news_backfill(session, known_urls=None, start_page=1, end_page=1070):
    documents = []

    for page in range(start_page, end_page + 1):
        url = "https://obs.ruse-bg.eu/news/" if page == 1 else NEWS_URL.format(page=page)
        print(f"Scraping news backfill page {page}...")
        html = get_page(session, url)

        if html is None:
            print(f"Page {page} returned 404, stopping")
            break

        page_documents = parse_news_feed(html, url)
        documents.extend(page_documents)

        time.sleep(REQUEST_DELAY_SECONDS)

    if known_urls is not None:
        new_count = sum(1 for doc in documents if doc["detail_url"] not in known_urls)
        print(f"{new_count} of {len(documents)} matched Решения documents are new")

    return documents

def parse_number_date(nd_raw):
    if not nd_raw or "/" not in nd_raw:
        return None, None
    number_part, date_part = nd_raw.rsplit("/", 1)
    try:
        datetime.strptime(date_part, "%Y-%m-%d")
        return number_part.strip(), date_part.strip()
    except ValueError:
        return number_part.strip(), None


def parse_archive_results(html, category_key, year, type_id):
    result_blocks = html.split('<div class="result">')[1:]
    documents = []

    for block in result_blocks:
        title_match = RESULT_TITLE_PATTERN.search(block)
        nd_match = RESULT_ND_PATTERN.search(block)
        pdf_match = RESULT_PDF_PATTERN.search(block)

        if not title_match:
            continue

        title = title_match.group(1).strip()
        nd_raw = nd_match.group(1).strip() if nd_match else None
        number_part, date_part = parse_number_date(nd_raw)
        pdf_url = pdf_match.group(1) if pdf_match else None

        documents.append({
            "title": title,
            "detail_url": pdf_url,
            "file_url": pdf_url,
            "file_type": "pdf" if pdf_url else None,
            "file_size_raw": None,
            "category": category_key,
            "publish_date_raw": date_part,
            "source_url": f"{ARCHIVE_URL}?year={year}&type={type_id}",
            "archive_number": number_part,
            "archive_source": True,
        })

    return documents, len(result_blocks)


def scrape_archive(session, known_urls=None):
    documents = []
    capped_combos = []

    session.get(ARCHIVE_URL, timeout=REQUEST_TIMEOUT)

    for year in ARCHIVE_YEARS:
        for type_id, category_key in ARCHIVE_TYPE_MAP.items():
            print(f"Searching archive: year={year} type={type_id}...")
            response = session.post(
                ARCHIVE_URL,
                data={"q": "", "year": str(year), "type": type_id},
                timeout=REQUEST_TIMEOUT,
            )
            results, count = parse_archive_results(response.text, category_key, year, type_id)

            is_capped = count == 10
            for doc in results:
                doc["possibly_incomplete"] = is_capped

            if is_capped:
                capped_combos.append((year, type_id, category_key))
                print(f"  CAPPED at 10 results, likely incomplete")

            documents.extend(results)
            time.sleep(REQUEST_DELAY_SECONDS)

    if known_urls is not None:
        new_count = sum(1 for d in documents if d["detail_url"] not in known_urls)
        print(f"{new_count} of {len(documents)} archive documents are new")

    print(f"{len(capped_combos)} of {len(ARCHIVE_YEARS) * len(ARCHIVE_TYPE_MAP)} year/type combinations hit the cap")
    return documents, capped_combos
    
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
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
        from src.db.connection import get_known_detail_urls
        from db.connection import get_known_detail_urls

        main(known_urls=get_known_detail_urls())
    else:
        main()
