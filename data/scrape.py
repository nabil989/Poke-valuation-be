import time
import re
import json
import sys
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://limitlesstcg.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}


def get_total_set_size(soup: BeautifulSoup, default: int) -> int:
    """Try to detect total number of cards shown on the set page."""
    m = re.search(r"(\d+)\s*Cards", soup.get_text(" ", strip=True), re.I)
    return int(m.group(1)) if m else default


def get_card_links(soup: BeautifulSoup, set_code: str) -> list[str]:
    """Find all card links for the given set code."""
    links = []
    for a in soup.select(f"div.card-search-grid a[href*='/cards/{set_code.upper()}/']"):
        href = a.get("href")
        if href:
            links.append(urljoin(BASE, href))
    seen, ordered = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered


def extract_name_from_detail(soup: BeautifulSoup) -> str | None:
    """Get card name from the detail page."""
    # Try main H1
    h1 = soup.select_one("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)

    # Try og:title
    og = soup.select_one('meta[property="og:title"]')
    if og and og.get("content"):
        return og["content"].split(" - ")[0].strip()

    # Try page title
    if soup.title and soup.title.string:
        return soup.title.string.split(" - ")[0].strip()

    return None


def scrape_set(set_code: str, total_cards: int):
    """Scrape all cards for a given set code like 'MEG'."""
    set_code = set_code.upper()
    set_url = f"{BASE}/cards/{set_code}"

    print(f"Fetching set page: {set_url}")
    session = requests.Session()
    session.headers.update(HEADERS)

    r = session.get(set_url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    detected_total = get_total_set_size(soup, total_cards)
    links = get_card_links(soup, set_code)

    print(f"Found {len(links)} card links; using total = {detected_total}")

    cards = []
    for idx, url in enumerate(links, start=1):
        num_match = re.search(rf"/cards/{set_code}/(\d+)$", url)
        num_str = f"{int(num_match.group(1)):03d}" if num_match else f"{idx:03d}"

        try:
            res = session.get(url, timeout=20)
            res.raise_for_status()
            detail = BeautifulSoup(res.text, "html.parser")
            name = extract_name_from_detail(detail) or f"{set_code} {num_str}"
        except Exception as e:
            print(f"  ! Failed to fetch {url}: {e}")
            name = f"{set_code} {num_str}"

        cards.append({
            "name": name,
            "number": num_str,
            "total": total_cards,
            "url": url
        })
        # time.sleep(0.25)  # Be polite

    out_json = f"{set_code.lower()}_cards.json"
    out_txt = f"{set_code.lower()}_cards.txt"

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    with open(out_txt, "w", encoding="utf-8") as f:
        for c in cards:
            f.write(f"{c['name']} {c['number']}/{c['total']}\n")

    print(f"Saved {len(cards)} cards → {out_json}, {out_txt}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 scrape_limitless_set.py <SET_CODE> <TOTAL_CARDS>")
        sys.exit(1)

    set_code = sys.argv[1]
    total_cards = int(sys.argv[2])
    scrape_set(set_code, total_cards)
