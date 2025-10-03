import os
import requests
from dotenv import load_dotenv

# load environment variables from .env
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

try:
    resp = requests.get("https://geo.brdtest.com/mygeo.json", proxies=proxies, timeout=10, verify=False)
    print("Response:", resp.json())
except Exception as e:
    print("Error:", e)
