import requests
from bs4 import BeautifulSoup
import json
import time
import os
from datetime import datetime

BASE_URL = "https://obs.ruse-bg.eu/document-category/{category}/page/{page}/"

CATEGORIES = {
    "naredbi": "наредби",
    "reshenia": "решения",
    "protokoli": "протоколи",
    "predlojenia": "предложения",
    "privatizacia": "приватизация",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


def fetch_page(category_slug, page_number):
    url = BASE_URL.format(category=category_slug, page=page_number)
    response = requests.get(url, headers=HEADERS, timeout=10)
    if response.status_code != 200:
        return None
    return response.text


def parse_documents(html, category_key, source_url):
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    articles = soup.find_all("article", class_="lsvr_document")

    for article in articles:
        title_tag = article.select_one("h2.post__title a.post__title-link")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        detail_url = title_tag.get("href")

        attachment_link = article.select_one("a.post__attachment-link")
        file_url = attachment_link.get("href") if attachment_link else None

        extension_tag = article.select_one("span.post__attachment-extension")
        file_type = None
        if extension_tag:
            file_type = extension_tag.get_text(strip=True).replace("File extension:", "").strip().lower()

        filesize_tag = article.select_one("span.post__attachment-filesize")
        file_size_raw = filesize_tag.get_text(strip=True) if filesize_tag else None

        date_tag = article.select_one("span.post__meta-date")
        publish_date_raw = date_tag.get_text(strip=True) if date_tag else None

        documents.append({
            "title": title,
            "detail_url": detail_url,
            "file_url": file_url,
            "file_type": file_type,
            "file_size_raw": file_size_raw,
            "category": category_key,
            "publish_date_raw": publish_date_raw,
            "source_url": source_url,
        })

    return documents


def scrape_category(category_slug, category_key, max_pages=3):
    all_documents = []

    for page in range(1, max_pages + 1):
        print(f"Scraping {category_key} page {page}...")
        html = fetch_page(category_slug, page)

        if html is None:
            print(f"No more pages for {category_key} at page {page}")
            break

        source_url = BASE_URL.format(category=category_slug, page=page)
        documents = parse_documents(html, category_key, source_url)

        if not documents:
            print(f"No documents found on page {page}, stopping.")
            break

        all_documents.extend(documents)
        time.sleep(1)

    return all_documents

def parse_reshenia_jsonld(html, source_url):
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    script_tags = soup.find_all("script", type="application/ld+json")

    for script in script_tags:
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
            publish_date_raw = None
            if date_published:
                publish_date_raw = date_published.split("T")[0]

            documents.append({
                "title": item.get("headline"),
                "detail_url": item.get("url"),
                "file_url": None,
                "file_type": None,
                "file_size_raw": None,
                "category": "reshenia",
                "publish_date_raw": publish_date_raw,
                "source_url": source_url,
                "description": item.get("description"),
            })

    return documents

def scrape_reshenia(max_pages=3):
    all_documents = []
    base = "https://obs.ruse-bg.eu/category/решения/"

    for page in range(1, max_pages + 1):
        url = base if page == 1 else f"{base}page/{page}/"
        print(f"Scraping reshenia page {page}...")

        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"No more pages for reshenia at page {page}")
            break

        documents = parse_reshenia_jsonld(response.text, url)

        if not documents:
            print(f"No documents found on page {page}, stopping.")
            break

        all_documents.extend(documents)
        time.sleep(1)

    return all_documents


def main():
    all_results = []

    category_slugs = {
        "naredbi": "наредби",
        "protokoli": "протоколи",
    }

    for key, slug in category_slugs.items():
        results = scrape_category(slug, key, max_pages=3)
        all_results.extend(results)

    reshenia_results = scrape_reshenia(max_pages=3)
    all_results.extend(reshenia_results)

    os.makedirs("data/raw", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"data/raw/scrape_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(all_results)} documents to {output_path}")
    return output_path


if __name__ == "__main__":
    main()