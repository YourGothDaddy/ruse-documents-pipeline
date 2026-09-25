import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

url = "https://obs.ruse-bg.eu/category/решения/"
response = requests.get(url, headers=HEADERS, timeout=10)

print(f"Status code: {response.status_code}")

with open("data/raw/sample_reshenia.html", "w", encoding="utf-8") as f:
    f.write(response.text)

print("Saved raw HTML to data/raw/sample_reshenia.html")