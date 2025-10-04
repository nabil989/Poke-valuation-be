import csv
import json
import os
import time
import requests
from playwright.sync_api import sync_playwright

from main import get_price_history, build_features

CACHE_FILE = "cache_tcg_ids.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def get_id_from_search(card_name, page=None, set_hint="Mega Evolution"):
    """
    Search TCGPlayer for a card and return the product ID.
    Uses cache and reuses browser session for speed.
    """
    cache = load_cache()
    if card_name in cache:
        return cache[card_name]

    search_query = f"{card_name} {set_hint}"
    search_url = f"https://www.tcgplayer.com/search/pokemon/product?productLineName=pokemon&q={search_query.replace(' ', '%20')}"

    try:
        page.goto(search_url, timeout=15000)
        page.wait_for_selector("a[href^='/product/']", timeout=7000)
        first_link = page.locator("a[href^='/product/']").first
        href = first_link.get_attribute("href")
        if not href:
            print(f"No product link for {card_name}")
            return None
        product_id = href.split("/product/")[1].split("/")[0]
        cache[card_name] = product_id
        save_cache(cache)
        return product_id
    except Exception as e:
        print(f"Search failed for {card_name}: {e}")
        return None


def get_card_metadata(card_id):
    """Fetch metadata (set name, number, release date) from Infinite API."""
    url = f"https://infinite-api.tcgplayer.com/products/{card_id}"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("result", {})
            return {
                "set_name": result.get("setName", ""),
                "number": result.get("number", ""),
                "release_date": result.get("releaseDate", "")
            }
    except Exception as e:
        print(f"Metadata fetch failed for {card_id}: {e}")
    return {"set_name": "", "number": "", "release_date": ""}


def collect_data(card_file, outfile="card_dataset.csv", default_buy=10.0):
    """Collect price + metadata for all cards in the given text file."""
    with open(card_file, "r", encoding="utf-8") as f:
        card_names = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(card_names)} cards from {card_file}")

    cache = load_cache()

    with open(outfile, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "card_name", "set_name", "number", "release_date",
            "recent_price", "old_price", "trend_pct",
            "recent_volume", "avg_volume", "volatility",
            "profit_margin", "roi_pct", "buy_price", "label"
        ])
        writer.writeheader()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for name in card_names:
                print(f"Processing: {name}")
                try:
                    # Use cache or lookup
                    card_id = cache.get(name) or get_id_from_search(name, page)
                    if not card_id:
                        print(f"Could not find ID for {name}")
                        continue

                    history = get_price_history(card_id)
                    if not history or "result" not in history:
                        print(f"No history for {name}")
                        continue

                    nm = [v for v in history["result"] if v.get("condition") == "Near Mint"]
                    if not nm:
                        print(f"No Near Mint data for {name}")
                        continue

                    features = build_features(nm[0]["buckets"], buy_price=default_buy)
                    if not features:
                        print(f"No features extracted for {name}")
                        continue

                    metadata = get_card_metadata(card_id)

                    profit = features["recent_price"] - default_buy
                    roi_pct = (profit / default_buy) * 100 if default_buy > 0 else 0
                    label = "SELL" if features["profit_margin"] >= 20 or features["trend_pct"] < -5 else "HOLD"

                    row = {
                        "card_name": name,
                        "set_name": metadata["set_name"],
                        "number": metadata["number"],
                        "release_date": metadata["release_date"],
                        "recent_price": features["recent_price"],
                        "old_price": features["old_price"],
                        "trend_pct": features["trend_pct"],
                        "recent_volume": features["recent_volume"],
                        "avg_volume": features["avg_volume"],
                        "volatility": features["volatility"],
                        "profit_margin": features["profit_margin"],
                        "roi_pct": roi_pct,
                        "buy_price": default_buy,
                        "label": label
                    }

                    writer.writerow(row)
                    print(f"Saved {name}")

                except Exception as e:
                    print(f"Error with {name}: {e}")

                time.sleep(0.5)  # polite pause

            browser.close()

    print(f"\nData collection complete. Saved to {outfile}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 collect_data_fast.py <card_file> [output.csv]")
        sys.exit(1)
    infile = sys.argv[1]
    outfile = sys.argv[2] if len(sys.argv) > 2 else "card_dataset.csv"
    collect_data(infile, outfile)
