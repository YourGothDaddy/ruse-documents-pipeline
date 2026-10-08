import argparse
import csv
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.db.connection import get_connection

OTHER = "Други теми"
MIN_SCORE = 1
BODY_MIN_CHARS = 200
BODY_CAP = 3

TOPIC_KEYWORDS = {
    "Устройство на територията": ["зут", "устройство на територията", "застрояв", "строеж", "урбанистич", "подробен устройствен"],
    "Общинска собственост": ["общинск собственост", "общинския имот", "общинско имущество", "концесия", "публичен търг", "наем", "частна общинск", "недвижим имот", "предоставяне за управление"],
    "Бюджет и финанси": ["бюджет", "субсиди", "капиталов", "дълг", "финансиране на"],
    "Образование": ["училищ", "детска градина", "детски градини", "детски ясли", "ясли", "образовани", "учебн", "предучилищ", "първи клас"],
    "Социални дейности": ["социални услуги", "социално подпомагане", "социал", "домашен помощник", "възрастни", "жилищни нужди", "социално настаняване"],
    "Транспорт": ["транспорт", "превоз", "автобус", "паркинг", "пътна мрежа", "велосипед"],
    "Околна среда": ["околна среда", "отпадък", "зелена система", "зелената система", "замърсяв", "дървет"],
    "Култура": ["читалищ", "музей", "театър", "културн", "паметник"],
    "Спорт": ["спорт", "физическа култура"],
    "Обществен ред": ["обществен ред", "масови обществени", "полиц"],
    "Местни данъци и такси": ["местни данъци", "данък", "данъч", "такс", "патентн", "таксиметров"],
}

LAW_TOPICS = {
    "ЗУТ": "Устройство на територията",
    "ЗОС": "Общинска собственост",
    "ЗМДТ": "Местни данъци и такси",
    "ЗПУО": "Образование",
    "ЗФВС": "Спорт",
}

def _stem_pattern(kw):
    words = kw.split()
    return r"\s+".join(r"(?<!\w)" + re.escape(w) + r"\w*" for w in words)

PATTERNS = {kw: re.compile(_stem_pattern(kw)) for kws in TOPIC_KEYWORDS.values() for kw in kws}


def normalise(text):
    return re.sub(r"\s+", " ", text or "").lower()


def hits(text, keywords):
    return {kw for kw in keywords if PATTERNS[kw].search(text)}


def score_document(doc, law_codes):
    title = normalise(doc["title"])
    description = normalise(doc["description"])
    body = normalise(doc["full_text"]) if doc["full_text"] and len(doc["full_text"]) >= BODY_MIN_CHARS else ""

    scores, evidence = {}, {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        title_hits = hits(title, keywords)
        desc_hits = hits(description, keywords)
        body_hits = hits(body, keywords) if body else set()
        law_hit = 2 if any(LAW_TOPICS.get(code) == topic for code in law_codes) else 0

        scores[topic] = (3 if title_hits else 0) + (2 if desc_hits else 0) \
            + min(len(body_hits), BODY_CAP) + law_hit
        
        strong_body = any(" " in kw or kw == "зут" for kw in body_hits)
        evidence[topic] = {
            "title_or_desc": bool(title_hits or desc_hits or law_hit),
            "body_hits": len(body_hits),
            "strong_body": strong_body,
        }
    return scores, evidence

def matched_keywords(doc, topic):
    """List the keywords that matched for the chosen topic, by source."""
    keywords = TOPIC_KEYWORDS.get(topic, [])
    sources = {
        "T": normalise(doc["title"]),
        "D": normalise(doc["description"]),
        "B": normalise(doc["full_text"]) if doc["full_text"] and len(doc["full_text"]) >= BODY_MIN_CHARS else "",
    }
    found = set()
    for label, text in sources.items():
        for kw in hits(text, keywords):
            found.add(f"{label}:{kw}")
    return "; ".join(sorted(found))

def all_topic_scores(doc, scores, evidence):
    """Debug: render every topic's score and evidence flags, for rows that land in OTHER."""
    parts = []
    for topic, score in sorted(scores.items(), key=lambda kv: -kv[1]):
        ev = evidence.get(topic, {})
        flag = "S" if ev.get("strong_body") else ("T" if ev.get("title_or_desc") else "")
        parts.append(f"{topic}:{score}{flag}")
    return "; ".join(parts)

def pick_topic(scores, evidence, category=None):
    if category == "Протоколи":
        return OTHER, 0
    max_score = max(scores.values())
    tied = [t for t in scores if scores[t] == max_score]
    def is_strong(t):
        ev = evidence.get(t, {})
        return ev.get("title_or_desc") or ev.get("strong_body") or ev.get("body_hits", 0) >= 2
    strong_tied = [t for t in tied if is_strong(t)]
    best_topic = strong_tied[0] if strong_tied else tied[0]
    if max_score < MIN_SCORE or not is_strong(best_topic):
        return OTHER, 0
    return best_topic, max_score

def main(dry_run=False):
    conn = get_connection(as_dict=True)

    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM topics")
        topic_ids = {row["name"]: row["id"] for row in cur.fetchall()}

        cur.execute("""
            SELECT d.id, d.title, d.description, d.full_text, c.name AS category
            FROM documents d
            LEFT JOIN categories c ON c.id = d.category_id
            ORDER BY d.id
        """)
        documents = cur.fetchall()

        cur.execute("SELECT document_id, law_code FROM document_law_references")
        laws = {}
        for row in cur.fetchall():
            laws.setdefault(row["document_id"], []).append(row["law_code"])

    missing = [t for t in list(TOPIC_KEYWORDS) + [OTHER] if t not in topic_ids]
    if missing:
        raise RuntimeError(f"Topics missing from table, run migration 013 first: {missing}")

    assignments = []
    summary = Counter()
    per_category = Counter()
    other_per_category = Counter()
    preview_rows = []

    for doc in documents:
        scores, evidence = score_document(doc, laws.get(doc["id"], []))
        topic, score = pick_topic(scores, evidence, doc["category"])
        assignments.append((doc["id"], topic_ids[topic]))
        summary[topic] += 1
        per_category[doc["category"]] += 1
        if topic == OTHER:
            other_per_category[doc["category"]] += 1
        preview_rows.append({
            "id": doc["id"],
            "category": doc["category"],
            "title": doc["title"],
            "topic": topic,
            "score": score,
            "matched": matched_keywords(doc, topic),
            "all_scores": all_topic_scores(doc, scores, evidence),
        })

    print(f"Classified {len(documents)} documents")
    for topic, count in summary.most_common():
        print(f"  {topic}: {count}")
    print("Други теми share by category:")
    for cat, total in per_category.most_common():
        print(f"  {cat}: {other_per_category[cat]}/{total}")

    if dry_run:
        os.makedirs("data/processed", exist_ok=True)
        path = os.path.join("data/processed", "topics_preview.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "category", "title", "topic", "score", "matched", "all_scores"])
            writer.writeheader()
            writer.writerows(preview_rows)
        print(f"Dry run: wrote {path}, database unchanged")
        conn.close()
        return

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_topics")
            cur.executemany(
                "INSERT INTO document_topics (document_id, topic_id) VALUES (%s, %s)",
                assignments,
            )
        conn.commit()
        print(f"Wrote {len(assignments)} topic assignments")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assign one topic per document.")
    parser.add_argument("--dry-run", action="store_true", help="Write a CSV preview, leave the database unchanged.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)