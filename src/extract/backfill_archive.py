import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from src.extract.scraper import build_session, scrape_archive
from src.db.connection import get_known_detail_urls


def main():
    known_urls = get_known_detail_urls()
    session = build_session()

    results, capped_combos = scrape_archive(session, known_urls=known_urls)

    new_only = [doc for doc in results if doc["detail_url"] not in known_urls and doc["detail_url"] is not None]
    print(f"Found {len(new_only)} genuinely new documents out of {len(results)} total")

    os.makedirs("data/raw", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"data/raw/backfill_archive_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(new_only, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_path}")

    if capped_combos:
        capped_path = f"data/raw/backfill_archive_capped_{timestamp}.json"
        with open(capped_path, "w", encoding="utf-8") as f:
            json.dump(capped_combos, f, ensure_ascii=False, indent=2)
        print(f"Capped combos (possibly incomplete) logged to {capped_path}")


if __name__ == "__main__":
    main()