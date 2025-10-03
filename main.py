import os
import requests
from dotenv import load_dotenv
import json
import urllib3
from playwright.sync_api import sync_playwright
import google.generativeai as genai

# silence SSL warnings for dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASS = os.getenv("PROXY_PASS")
PROXY_HOST = os.getenv("PROXY_HOST")
PROXY_PORT = os.getenv("PROXY_PORT")

proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

proxies = {
    "http": proxy_url,
    "https": proxy_url,
}

headers = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://infinite.tcgplayer.com/",
    "Origin": "https://infinite.tcgplayer.com",
}

def get_id_from_search(card_name):
    search_url = f"https://www.tcgplayer.com/search/all/product?q={card_name.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(search_url, timeout=60000)
        
        # wait for any product link (href starts with /product/)
        page.wait_for_selector("a[href^='/product/']", timeout=60000)
        
        href = page.query_selector("a[href^='/product/']").get_attribute("href")
        browser.close()
        
        if href and href.startswith("/product/"):
            parts = href.split("/")
            if len(parts) > 2:
                return parts[2]  # product ID
    return None

def get_price_history(id, range="annual", dev=False):
    url = f"https://infinite-api.tcgplayer.com/price/history/{id}/detailed?range={range}"
    try:
        resp = requests.get(url, proxies=proxies, timeout=10, headers=headers, verify=False)
        if dev:
            print("Status:", resp.status_code)
            print("Headers:", resp.headers)
            print("Response JSON:", resp.json())
        return resp.json()
    except Exception as e:
        return ("error:", e)
    
def analyze_card(card_history, buy_price, condition="Near Mint"):
    """
    card_history: JSON dict from TCGplayer API
    buy_price: what you paid for the card
    condition: which condition to analyze (default Near Mint)
    """
    if not card_history or "result" not in card_history:
        return "No data available"

    # Pick condition variant
    variants = [v for v in card_history["result"] if v.get("condition") == condition]
    if not variants:
        return f"No data available for condition {condition}"
    
    buckets = variants[0].get("buckets", [])
    if not buckets:
        return "No price buckets available"

    # Convert strings → floats/ints
    prices = [float(b["marketPrice"]) for b in buckets if float(b["marketPrice"]) > 0]
    volumes = [int(b["transactionCount"]) for b in buckets if int(b["transactionCount"]) > 0]

    if not prices:
        return "No valid market prices available"

    # Most recent = first entry
    recent_price = prices[0]
    old_price = prices[-1]
    trend = (recent_price - old_price) / old_price * 100 if old_price > 0 else 0

    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    recent_volume = volumes[0] if volumes else 0

    # Decision logic
    if recent_price >= buy_price * 1.2:
        decision = "SELL"
        reason = f"Price is {recent_price:.2f}, at least 20% above your buy price {buy_price:.2f}."
    elif trend > 5 and recent_volume > avg_volume:
        decision = "HOLD"
        reason = f"Price trending up {trend:.1f}% with strong volume."
    elif trend < -5:
        decision = "SELL"
        reason = f"Price trending down {trend:.1f}%."
    else:
        decision = "HOLD"
        reason = f"Price stable at {recent_price:.2f}, no strong signals."

    return {
        "condition": condition,
        "decision": decision,
        "trend_pct": trend,
        "recent_price": recent_price,
        "old_price": old_price,
        "reason": reason,
    }

def rule_based_recommendation(features, buy_price):
    """
    features: dict from build_features()
    buy_price: float
    """
    recent = features["recent_price"]
    trend = features["trend_pct"]
    profit = features["profit_margin"]
    recent_volume = features["recent_volume"]
    avg_volume = features["avg_volume"]

    if profit >= 20:  # 20%+ profit
        return "SELL", f"Price is ${recent:.2f}, profit margin {profit:.1f}%."
    if trend < -5:  # downward trend
        return "SELL", f"Price trending down {trend:.1f}%."
    if trend > 5 and recent_volume > avg_volume:
        return "HOLD", f"Price rising {trend:.1f}% with strong demand."
    return "HOLD", f"Price stable at ${recent:.2f}, no strong signals."

def build_features(buckets, buy_price):
    prices = [float(b["marketPrice"]) for b in buckets if b.get("marketPrice")]
    volumes = [int(b["transactionCount"]) for b in buckets if b.get("transactionCount")]

    if not prices:
        return {}

    recent_price = prices[0]
    old_price = prices[-1]
    trend_pct = (recent_price - old_price) / old_price * 100 if old_price > 0 else 0

    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    recent_volume = volumes[0] if volumes else 0
    volatility = (max(prices) - min(prices)) / (sum(prices)/len(prices)) * 100 if prices else 0
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


card_id = get_id_from_search("parasol lady 255/182")
card_history = get_price_history(card_id)
# save to file
# with open("card_history.json", "w") as f:
#     json.dump(card_history, f, indent=2)
# print(analyze_card(card_history, 10))
# print("parasol lady:", get_price_history(get_id_from_search("parasol lady 255/182")))

nm_variant = [v for v in card_history["result"] if v.get("condition") == "Near Mint"]
if nm_variant:
    features = build_features(nm_variant[0]["buckets"], buy_price=10)
    decision, reason = rule_based_recommendation(features, buy_price=10)
    print("Rule Decision:", decision, "-", reason)





