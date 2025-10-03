import requests

def get_card_info(card_name):
    url = f"https://api.pokemontcg.io/v2/cards?q=name:{card_name}"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()["data"]
        cards = []
        for c in data:
            cards.append({
                "name": c["name"],
                "number": c["number"],
                "set": c["set"]["name"],
                "release": c["set"]["releaseDate"]
            })
        return cards
    else:
        return {"error": "Card not found"}

print(get_card_info("Riolu"))