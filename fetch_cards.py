import requests
import time
import csv

POKEMON_TCG_API = "https://api.pokemontcg.io/v2/cards"

def fetch_all_cards(limit=5000):
    """Fetch all Pokémon cards from the Pokémon TCG API."""
    cards = []
    page = 1

    while True:
        url = f"{POKEMON_TCG_API}?page={page}&pageSize=5"  # max pageSize = 250
        resp = requests.get(url)
        if resp.status_code != 200:
            print("Error:", resp.status_code, resp.text)
            break
        
        data = resp.json()
        if "data" not in data or not data["data"]:
            break

        for card in data["data"]:
            cards.append({
                "name": card["name"],
                "number": card.get("number", ""),
                "set": card["set"]["name"],
                "release": card["set"].get("releaseDate", ""),
            })
        
        print(f"Fetched page {page}, total {len(cards)} cards")

        if len(cards) >= limit or len(data["data"]) < 250:
            break

        page += 1
        time.sleep(0.3)  # rate-limit friendly

    return cards


def save_cards(cards, outfile="all_cards.csv"):
    """Save card list to CSV for later use."""
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "number", "set", "release"])
        writer.writeheader()
        writer.writerows(cards)
    print(f"Saved {len(cards)} cards to {outfile}")


if __name__ == "__main__":
    all_cards = fetch_all_cards(limit=10000)  
    save_cards(all_cards)
