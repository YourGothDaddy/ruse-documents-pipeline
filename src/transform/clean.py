import json
import glob
import re
import html
from datetime import datetime

CATEGORY_MAP = {
    "naredbi": "Наредби",
    "reshenia": "Решения",
    "protokoli": "Протоколи",
    "predlojenia": "Предложения",
    "privatizacia": "Приватизация",
}

REPEALED_KEYWORDS = ["отменена", "отменен", "отменени"]


def parse_date(raw_date, category_key):
    if not raw_date:
        return None

    if category_key == "reshenia":
        try:
            return datetime.strptime(raw_date, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None

    try:
        return datetime.strptime(raw_date, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def parse_file_size(raw_size):
    if not raw_size:
        return None

    match = re.match(r"([\d.]+)\s*(kB|MB)", raw_size, re.IGNORECASE)
    if not match:
        return None

    value, unit = match.groups()
    value = float(value)

    if unit.lower() == "mb":
        return int(value * 1024)
    return int(value)


def detect_status(title):
    title_lower = title.lower()
    for keyword in REPEALED_KEYWORDS:
        if keyword in title_lower:
            return "repealed"
    return "active"


def clean_title(title):
    if not title:
        return title
    cleaned = html.unescape(title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def transform_document(raw_doc):
    title = clean_title(raw_doc.get("title"))

    return {
        "title": title,
        "category_name": CATEGORY_MAP.get(raw_doc.get("category")),
        "status_name": detect_status(title),
        "publish_date": parse_date(raw_doc.get("publish_date_raw"), raw_doc.get("category")),
        "file_url": raw_doc.get("file_url"),
        "file_type": raw_doc.get("file_type"),
        "file_size_kb": parse_file_size(raw_doc.get("file_size_raw")),
        "source_url": raw_doc.get("source_url"),
        "detail_url": raw_doc.get("detail_url"),
    }


def deduplicate(documents):
    seen = set()
    unique_documents = []

    for doc in documents:
        key = doc["detail_url"]
        if key in seen:
            continue
        seen.add(key)
        unique_documents.append(doc)

    return unique_documents


def main():
    raw_files = sorted(glob.glob("data/raw/scrape_*.json"))
    latest_file = raw_files[-1]

    print(f"Reading {latest_file}")

    with open(latest_file, encoding="utf-8") as f:
        raw_documents = json.load(f)

    transformed = [transform_document(doc) for doc in raw_documents]
    transformed = deduplicate(transformed)

    missing_dates = sum(1 for d in transformed if d["publish_date"] is None)
    repealed_count = sum(1 for d in transformed if d["status_name"] == "repealed")

    print(f"Transformed {len(transformed)} unique documents")
    print(f"Missing dates: {missing_dates}")
    print(f"Repealed: {repealed_count}")

    output_path = latest_file.replace("data/raw/scrape_", "data/processed/clean_")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transformed, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()