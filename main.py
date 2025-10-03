import os
import requests
import json
import urllib3
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import google.generativeai as genai

# silence SSL warnings for dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# load environment variables
load_dotenv()

# proxy config
PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASS = os.getenv("PROXY_PASS")
PROXY_HOST = os.getenv("PROXY_HOST")
PROXY_PORT = os.getenv("PROXY_PORT")

proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
proxies = {"http": proxy_url, "https": proxy_url}

# request headers
headers = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://infinite.tcgplayer.com/",
    "Origin": "https://infinite.tcgplayer.com",
}

# configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-flash-latest")


# ---------- Scraping ----------
def get_id_from_search(card_name: str):
    """Search TCGPlayer for a card and return its product ID."""
    search_url = f"https://www.tcgplayer.com/search/all/product?q={card_name.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(search_url, timeout=60000)

        page.wait_for_selector("a[href^='/product/']", timeout=60000)
        href = page.query_selector("a[href^='/product/']").get_attribute("href")
        browser.close()

        if href and href.startswith("/product/"):
            parts = href.split("/")
            if len(parts) > 2:
                return parts[2]  # product ID
    return None


def get_price_history(product_id: str, range="annual", dev=False):
    """Fetch price history for a given product ID."""
    url = f"https://infinite-api.tcgplayer.com/price/history/{product_id}/detailed?range={range}"
    try:
        resp = requests.get(url, proxies=proxies, timeout=10, headers=headers, verify=False)
        if dev:
            print("Status:", resp.status_code)
            print("Headers:", resp.headers)
            print("Response JSON:", resp.json())
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


# ---------- Feature Engineering ----------
def build_features(buckets, buy_price: float | None):
    """Convert price history buckets into numeric features."""
    prices = [float(b["marketPrice"]) for b in buckets if b.get("marketPrice")]
    volumes = [int(b["transactionCount"]) for b in buckets if b.get("transactionCount")]

    if not prices:
        return {}

    recent_price = prices[0]
    old_price = prices[-1]
    trend_pct = (recent_price - old_price) / old_price * 100 if old_price > 0 else 0
    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    recent_volume = volumes[0] if volumes else 0
    volatility = (max(prices) - min(prices)) / (sum(prices) / len(prices)) * 100 if prices else 0

    profit_margin = None
    if buy_price:  # only compute if card was bought
        profit_margin = (recent_price - buy_price) / buy_price * 100

    return {
        "recent_price": recent_price,
        "old_price": old_price,
        "trend_pct": trend_pct,
        "recent_volume": recent_volume,
        "avg_volume": avg_volume,
        "volatility": volatility,
        "profit_margin": profit_margin,
    }


# ---------- Rule-Based Recommendation ----------
def rule_based_recommendation(features, buy_price: float | None):
    """Decision rules for HOLD/SELL. Adapts if buy_price is missing (pulled card)."""
    recent = features["recent_price"]
    trend = features["trend_pct"]
    recent_volume = features["recent_volume"]
    avg_volume = features["avg_volume"]

    if buy_price:  # Bought directly
        profit = features["profit_margin"]
        if profit >= 20:
            return "SELL", f"Price is ${recent:.2f}, profit margin {profit:.1f}%."
        if trend < -5:
            return "SELL", f"Price trending down {trend:.1f}%."
        if trend > 5 and recent_volume > avg_volume:
            return "HOLD", f"Price rising {trend:.1f}% with strong demand."
        return "HOLD", f"Stable at ${recent:.2f}, no strong signals."

    else:  # Pulled from a pack
        if trend > 5 and recent_volume > avg_volume:
            return "HOLD", f"Trending up {trend:.1f}% with strong demand."
        if trend < -5:
            return "SELL", f"Trending down {trend:.1f}%, value may keep dropping."
        return "HOLD", f"Stable at ${recent:.2f}, no strong signals."


# ---------- AI Summarizer ----------
def ai_recommendation(card_name: str, features: dict, decision: str, reason: str):
    """Generate a natural language recommendation using Gemini."""
    prompt = f"""
    Card: {card_name}
    Features: {features}
    Rule-based decision: {decision} ({reason}).

    Provide a concise recommendation for a Pokémon card trader
    about whether to SELL or HOLD this card, assuming it was {'bought' if features.get("profit_margin") is not None else 'pulled from a pack'}.
    """
    response = model.generate_content(prompt)
    return response.text


# ---------- Main ----------
def main():
    card_name = input("Enter card name: ").strip()
    mode = input("Did you buy this card or pull it from a pack? (buy/pull): ").strip().lower()

    buy_price = None
    if mode == "buy":
        try:
            buy_price = float(input("Enter your buy price: "))
        except ValueError:
            print("Invalid buy price. Defaulting to None.")

    card_id = get_id_from_search(card_name)
    if not card_id:
        print("Could not find product ID.")
        return

    history = get_price_history(card_id)
    if not history or "result" not in history:
        print("No price history found.")
        return

    nm = [v for v in history["result"] if v.get("condition") == "Near Mint"]
    if not nm:
        print("No Near Mint data.")
        return

    features = build_features(nm[0]["buckets"], buy_price)
    if not features:
        print("No valid features extracted.")
        return

    decision, reason = rule_based_recommendation(features, buy_price)
    summary = ai_recommendation(card_name, features, decision, reason)

    print("\n--- Analysis ---")
    print("Rule Decision:", decision, "-", reason)
    print("AI Recommendation:", summary)


if __name__ == "__main__":
    main()
