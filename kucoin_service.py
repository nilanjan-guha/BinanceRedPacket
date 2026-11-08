import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY", "6aec8d7bb2e9670001ba6a4a")
KUCOIN_API_SECRET = os.getenv("KUCOIN_API_SECRET", "80092593-8965-4e96-82f6-4b00ecc2189d")

# KuCoin Open API Base URLs with fallback mirrors
KUCOIN_HOSTS = [
    "https://openapi-v2.kucoin.com",
    "https://api.kucoin.com"
]

class KuCoinClient:
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key or KUCOIN_API_KEY
        self.api_secret = api_secret or KUCOIN_API_SECRET
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 KuCoinInspector/1.0",
            "Content-Type": "application/json"
        })
        self.active_base_url = "https://openapi-v2.kucoin.com"

    def request(self, method: str, path: str, params: dict = None, timeout: int = 5):
        params = params or {}
        urls = [self.active_base_url] + [u for u in KUCOIN_HOSTS if u != self.active_base_url]
        last_err = None

        for base in urls:
            try:
                url = f"{base}{path}"
                res = self.session.request(method, url, params=params, timeout=timeout)
                if res.status_code == 200:
                    self.active_base_url = base
                    return res.json()
                else:
                    last_err = f"Status {res.status_code}: {res.text[:80]}"
            except Exception as e:
                last_err = str(e)
                continue

        return {"code": "500", "msg": last_err or "Connection failed"}

    def get_all_tickers(self):
        """Fetches all spot market tickers from KuCoin"""
        res = self.request("GET", "/api/v1/market/allTickers")
        if res.get("code") == "200000":
            return res.get("data", {}).get("ticker", [])
        return []

    def get_order_book(self, symbol="BTC-USDT"):
        """Fetches Level 2 Depth (top 20 bids/asks)"""
        res = self.request("GET", f"/api/v1/market/orderbook/level2_20", params={"symbol": symbol})
        if res.get("code") == "200000":
            return res.get("data", {})
        return {"bids": [], "asks": []}

    def get_recent_trades(self, symbol="BTC-USDT"):
        """Fetches recent public executed trades"""
        res = self.request("GET", "/api/v1/market/histories", params={"symbol": symbol})
        if res.get("code") == "200000":
            return res.get("data", [])
        return []

    def get_ticker_24h(self, symbol="BTC-USDT"):
        """Fetches 24hr stats for single symbol"""
        res = self.request("GET", "/api/v1/market/stats", params={"symbol": symbol})
        if res.get("code") == "200000":
            return res.get("data", {})
        return {}

