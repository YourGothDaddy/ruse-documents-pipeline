import re
import subprocess

RATE_PATTERN = re.compile(
    r"Данъкът\s+върху\s+недвижимите\s+имоти\s+е\s+в\s+размер\s+на\s+(\d+(?:[.,]\d+)?)\s+на\s+хиляда",
    re.IGNORECASE
)


def extract_text(doc_path):
    result = subprocess.run(
        ["antiword", doc_path],
        capture_output=True, text=True, check=True
    )
    return result.stdout


def parse_property_tax_rate(text):
    match = RATE_PATTERN.search(text)
    if not match:
        return None
    rate_str = match.group(1).replace(",", ".")
    return float(rate_str)


if __name__ == "__main__":
    import sys
    text = extract_text(sys.argv[1])
    rate = parse_property_tax_rate(text)
    print(f"Property tax rate: {rate} на хиляда" if rate else "Rate not found")