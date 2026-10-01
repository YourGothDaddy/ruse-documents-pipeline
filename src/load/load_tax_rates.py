import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from src.db.connection import get_connection
from src.extract.parse_tax_rate import extract_text, parse_property_tax_rate

NAREDBA_20_PATH = "data/raw/tax_docs/naredba_20.doc"
NAREDBA_20_DETAIL_URL = "https://obs.ruse-bg.eu/wp-content/uploads/2024/12/20.doc"


def load_property_tax_rate(doc_path=NAREDBA_20_PATH):
    text = extract_text(doc_path)
    rate = parse_property_tax_rate(text)

    if rate is None:
        raise RuntimeError(f"Could not parse property tax rate from {doc_path}, check if source document format or wording changed")

    conn = get_connection(as_dict=True)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tax_rates (tax_type, rate, rate_unit, source_document, last_checked)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (tax_type) DO UPDATE SET
                    rate = EXCLUDED.rate,
                    rate_unit = EXCLUDED.rate_unit,
                    source_document = EXCLUDED.source_document,
                    last_checked = NOW()
            """, ("property_tax", rate, "per_mille", NAREDBA_20_DETAIL_URL))
        conn.commit()
        print(f"Property tax rate loaded: {rate} per_mille")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    load_property_tax_rate()