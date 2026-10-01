import json
import os
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

BULGARIAN_MONTHS = {
    "януари": 1, "февруари": 2, "март": 3, "април": 4,
    "май": 5, "юни": 6, "юли": 7, "август": 8,
    "септември": 9, "октомври": 10, "ноември": 11, "декември": 12,
}

RESHENIA_PATTERN = re.compile(
    r"№\s*(\d+)\s*Прието\s+с\s+Протокол\s*№\s*(\d+)\s*/\s*(\d{2})\.(\d{2})\.(\d{4})",
    re.IGNORECASE
)

RESHENIA_NUMBER_ONLY_PATTERN = re.compile(
    r"№\s*(\d+)",
    re.IGNORECASE
)

NAREDBA_PATTERN = re.compile(
    r"[НH]аредб[а-я]*\s*№\s*(\d+)",
    re.IGNORECASE
)

PROTOKOL_NUMBER_DIGIT_PATTERN = re.compile(
    r"ПРОТОКОЛ\s*№?\s*(\d+)",
    re.IGNORECASE
)

PROTOKOL_NUMBER_WORD_PATTERN = re.compile(
    r"ПРОТОКОЛ\s+ОТ\s+([а-я\s]+?)(?:\s+ИЗВЪНРЕДНОТО)?\s+ЗАСЕДАНИЕ",
    re.IGNORECASE
)

BULGARIAN_ORDINAL_WORDS = {
    "първото": 1, "второто": 2, "третото": 3, "четвъртото": 4, "петото": 5,
    "шестото": 6, "седмото": 7, "осмото": 8, "деветото": 9, "десетото": 10,
    "единадесетото": 11, "дванадесетото": 12, "тринадесетото": 13,
    "четиринадесетото": 14, "петнадесетото": 15, "шестнадесетото": 16,
    "седемнадесетото": 17, "осемнадесетото": 18, "деветнадесетото": 19,
    "двадесетото": 20, "двадесет и първото": 21, "двадесет и второто": 22,
    "двадесет и третото": 23, "двадесет и четвъртото": 24, "двадесет и петото": 25,
    "двадесет и шестото": 26, "двадесет и седмото": 27, "двадесет и осмото": 28,
    "двадесет и деветото": 29, "тридесетото": 30, "тридесет и първото": 31,
    "тридесет и второто": 32, "тридесет и третото": 33, "тридесет и четвъртото": 34,
    "тридесет и петото": 35, "тридесет и шестото": 36, "тридесет и седмото": 37,
    "тридесет и осмото": 38, "тридесет и деветото": 39, "четиридесетото": 40,
}

TOPIC_KEYWORDS = {
    "Устройство на територията": ["зут", "устройство на територията", "застрояване", "кадастър", "строеж"],
    "Общинска собственост": ["общинска собственост", "концесия", "наем", "продажба на имот", "разпореждане с имот"],
    "Бюджет и финанси": ["бюджет", "разходи", "приходи", "субсидия", "капиталови разходи"],
    "Образование": ["училище", "детска градина", "образование", "учебна"],
    "Социални дейности": ["социални услуги", "социално подпомагане", "домашен помощник", "възрастни хора"],
    "Транспорт": ["транспортна схема", "автобусни линии", "пътна", "паркинг"],
    "Околна среда": ["околна среда", "отпадъци", "замърсяване", "зелена система"],
    "Култура": ["културна", "читалище", "музей", "театър"],
}

LAW_CODE_PATTERN = re.compile(
    r"\b(ЗМСМА|ЗУТ|ЗОС|ЗМДТ|ЗОП|АПК|ТЗ|ЗДДС)\b",
    re.IGNORECASE
)

PROTOKOL_DATE_PATTERN = re.compile(
    r"проведено\s+на\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})",
    re.IGNORECASE
)

PROTOKOL_DATE_WORD_PATTERN = re.compile(
    r"проведено\s+на\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})",
    re.IGNORECASE
)

PROTOKOL_DATE_NUMERIC_PATTERN = re.compile(
    r"проведено\s+на\s+(\d{2})\.(\d{2})\.(\d{4})",
    re.IGNORECASE
)

def parse_date(raw_date, category_key):
    if not raw_date:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw_date, fmt).date().isoformat()
        except ValueError:
            continue

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

def assign_topics(title, description):
    text = (title or "") + " " + (description or "")
    text_lower = text.lower()

    matched_topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            matched_topics.append(topic)

    return matched_topics


def extract_law_references(description):
    if not description:
        return []
    matches = LAW_CODE_PATTERN.findall(description)
    return sorted(set(match.upper() for match in matches))

def detect_status(title):
    title_lower = title.lower()
    for keyword in REPEALED_KEYWORDS:
        if keyword in title_lower:
            return "repealed"
    return "active"

def parse_reshenia_fields(title):
    match = RESHENIA_PATTERN.search(title)
    if match:
        decision_number = int(match.group(1))
        protocol_number = int(match.group(2))
        day, month, year = match.group(3), match.group(4), match.group(5)

        try:
            session_date = datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y").date().isoformat()
        except ValueError:
            session_date = None

        return decision_number, protocol_number, session_date

    number_only_match = RESHENIA_NUMBER_ONLY_PATTERN.search(title)
    if number_only_match:
        return int(number_only_match.group(1)), None, None

    return None, None, None


def parse_naredba_number(title):
    match = NAREDBA_PATTERN.search(title)
    if not match:
        return None
    return int(match.group(1))

def parse_protokol_fields(title):
    protocol_number = None

    digit_match = PROTOKOL_NUMBER_DIGIT_PATTERN.search(title)
    if digit_match:
        protocol_number = int(digit_match.group(1))
    else:
        word_match = PROTOKOL_NUMBER_WORD_PATTERN.search(title)
        if word_match:
            word = word_match.group(1).strip().lower()
            protocol_number = BULGARIAN_ORDINAL_WORDS.get(word)

    session_date = None

    word_date_match = PROTOKOL_DATE_WORD_PATTERN.search(title)
    if word_date_match:
        day = int(word_date_match.group(1))
        month_name = word_date_match.group(2).lower()
        year = int(word_date_match.group(3))
        month = BULGARIAN_MONTHS.get(month_name)
        if month:
            try:
                session_date = datetime(year, month, day).date().isoformat()
            except ValueError:
                session_date = None

    if session_date is None:
        numeric_date_match = PROTOKOL_DATE_NUMERIC_PATTERN.search(title)
        if numeric_date_match:
            day, month, year = numeric_date_match.groups()
            try:
                session_date = datetime(int(year), int(month), int(day)).date().isoformat()
            except ValueError:
                session_date = None

    return protocol_number, session_date

def clean_title(title):
    if not title:
        return title
    cleaned = html.unescape(title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def transform_document(raw_doc):
    title = clean_title(raw_doc.get("title"))
    category = raw_doc.get("category")

    decision_number = protocol_number = regulation_number = session_date = None

    if category == "reshenia":
        decision_number, protocol_number, session_date = parse_reshenia_fields(title)
    elif category == "naredbi":
        regulation_number = parse_naredba_number(title)
    elif category == "protokoli":
        protocol_number, session_date = parse_protokol_fields(title)

    return {
        "title": title,
        "category_name": CATEGORY_MAP.get(category),
        "status_name": detect_status(title),
        "publish_date": parse_date(raw_doc.get("publish_date_raw"), category),
        "file_url": raw_doc.get("file_url"),
        "file_type": raw_doc.get("file_type"),
        "file_size_kb": parse_file_size(raw_doc.get("file_size_raw")),
        "source_url": raw_doc.get("source_url"),
        "detail_url": raw_doc.get("detail_url"),
        "description": html.unescape(raw_doc.get("description")) if raw_doc.get("description") else None,
        "decision_number": decision_number,
        "protocol_number": protocol_number,
        "regulation_number": regulation_number,
        "session_date": session_date,
        "topics": assign_topics(title, raw_doc.get("description")),
        "law_references": extract_law_references(raw_doc.get("description")),
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


def main(input_path=None):
    if input_path is None:
        raw_files = sorted(glob.glob("data/raw/scrape_*.json"))
        input_path = raw_files[-1]

    print(f"Reading {input_path}")

    with open(input_path, encoding="utf-8") as f:
        raw_documents = json.load(f)

    transformed = [transform_document(doc) for doc in raw_documents]
    transformed = deduplicate(transformed)

    missing_dates = sum(1 for d in transformed if d["publish_date"] is None)
    repealed_count = sum(1 for d in transformed if d["status_name"] == "repealed")

    reshenia_docs = [d for d in transformed if d["category_name"] == "Решения"]
    naredbi_docs = [d for d in transformed if d["category_name"] == "Наредби"]
    protokoli_docs = [d for d in transformed if d["category_name"] == "Протоколи"]

    reshenia_parsed = sum(1 for d in reshenia_docs if d["decision_number"] is not None)
    naredbi_parsed = sum(1 for d in naredbi_docs if d["regulation_number"] is not None)
    protokoli_parsed = sum(1 for d in protokoli_docs if d["protocol_number"] is not None)

    print(f"Transformed {len(transformed)} unique documents")
    print(f"Missing dates: {missing_dates}")
    print(f"Repealed: {repealed_count}")
    if reshenia_docs:
        print(f"Решения decision numbers parsed: {reshenia_parsed}/{len(reshenia_docs)}")
    if naredbi_docs:
        print(f"Наредби regulation numbers parsed: {naredbi_parsed}/{len(naredbi_docs)}")
    if protokoli_docs:
        print(f"Протоколи protocol numbers parsed: {protokoli_parsed}/{len(protokoli_docs)}")

    tagged_count = sum(1 for d in transformed if d["topics"])
    with_law_refs = sum(1 for d in transformed if d["law_references"])

    print(f"Documents with at least one topic: {tagged_count}/{len(transformed)}")
    print(f"Documents with at least one law reference: {with_law_refs}/{len(transformed)}")

    input_filename = os.path.basename(input_path)
    timestamp_match = re.search(r"\d{8}_\d{6}", input_filename)
    if not timestamp_match:
        raise ValueError(f"Could not find a timestamp in input filename: {input_filename}")
    output_filename = f"clean_{timestamp_match.group(0)}.json"
    output_path = os.path.join("data/processed", output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transformed, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_path}")
    return output_path

if __name__ == "__main__":
    main()