import os
import requests
from dotenv import load_dotenv
import urllib3

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

def get_price_history(id, range="annual"):
    url = f"https://infinite-api.tcgplayer.com/price/history/{id}/detailed?range={range}"
    try:
        resp = requests.get(url, proxies=proxies, timeout=10, headers=headers, verify=False)
        # print("Status:", resp.status_code)
        # print("Headers:", resp.headers)
        # print("Response JSON:", resp.json())
        return resp.json()
    except Exception as e:
        return ("error:", e)
print(get_price_history(632987))



