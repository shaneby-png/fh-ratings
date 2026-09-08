"""
Fetches the live schedule/results page from FinalWhistleFH.com for a given
division and year, and returns it as plain text ready for scraper.parse_games().

NOTE: This makes a real network call and must be run in an environment with
open internet access (this will NOT work inside a sandboxed tool runner with
a domain allowlist -- run it from your own machine / server / cron job).
"""
import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; FHRatingsBot/1.0; personal research script)"


def fetch_schedule_text(division: int = 1, year: int = 2026) -> str:
    url = f"https://www.finalwhistlefh.com/d{division}/{year}/all-dates"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Strip script/style noise, then flatten to text in DOM order -- the
    # parser in scraper.py is regex-based over this flattened text.
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


if __name__ == "__main__":
    import sys
    div = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    yr = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    text = fetch_schedule_text(div, yr)
    print(text[:2000])
