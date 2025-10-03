import csv
import time
import requests
from main import get_id_from_search, get_price_history, build_features

# Example set of cards
CARD_NAMES = [
    "Ivysaur 134/132",
    "Parasol Lady 255/182",
    "Riolu 010"
]

def get_card_metadata(card_id):
    """Fetch extra card metadata from TCGPlayer product page (set name, number, release)."""
    url = f"https://infinite-api.tcgplayer.com/products/{card_id}"
    try:
        resp = requests.get(url, timeout=10)
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


def collect_data(card_names, outfile="card_dataset.csv", default_buy=10.0):
    with open(outfile, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "card_name", "set_name", "number", "release_date",
            "recent_price", "old_price", "trend_pct",
            "recent_volume", "avg_volume", "volatility",
            "profit_margin", "roi_pct", "buy_price", "label"
        ])
        writer.writeheader()

        for name in card_names:
            print(f"Processing: {name}")
            try:
                card_id = get_id_from_search(name)
                if not card_id:
                    print(f"Could not find ID for {name}")
                    continue

                history = get_price_history(card_id)
                if not history or "result" not in history:
                    print(f"No history for {name}")
                    continue

                # Focus on Near Mint condition
                nm = [v for v in history["result"] if v.get("condition") == "Near Mint"]
                if not nm:
                    print(f"No Near Mint data for {name}")
                    continue

                features = build_features(nm[0]["buckets"], buy_price=default_buy)
                if not features:
                    print(f"No features extracted for {name}")
                    continue

                # Extra metadata
                metadata = get_card_metadata(card_id)

                # Profit and ROI
                profit = features["recent_price"] - default_buy
                roi_pct = (profit / default_buy) * 100 if default_buy > 0 else 0

                # Label: create SELL/HOLD labels for ML training
                if features["profit_margin"] >= 20 or features["trend_pct"] < -5:
                    label = "SELL"
                else:
                    label = "HOLD"

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

                time.sleep(2)

            except Exception as e:
                print(f"Error with {name}: {e}")

    print(f"\nData collection complete. Saved to {outfile}")


if __name__ == "__main__":
    collect_data(CARD_NAMES)
