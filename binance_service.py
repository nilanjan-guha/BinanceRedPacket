import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Fallback base endpoints (api.binance.me is reliable when api.binance.com is geo-filtered/firewalled)
BASE_URLS = [
    "https://api.binance.me",
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api3.binance.com"
]

class BinanceClient:
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key or BINANCE_API_KEY
        self.api_secret = api_secret or BINANCE_API_SECRET
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 BinanceDataInspector/1.0",
            "X-MBX-APIKEY": self.api_key
        })
        self.active_base_url = "https://api.binance.me"

    def _sign(self, params: dict):
        params["timestamp"] = int(time.time() * 1000)
        # recvWindow protects against clock drift
        params["recvWindow"] = 60000
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def request(self, method: str, path: str, params: dict = None, signed: bool = False, timeout: int = 6):
        params = params or {}
        urls = [self.active_base_url] + [u for u in BASE_URLS if u != self.active_base_url]
        last_error = None
        
        for base in urls:
            try:
                if signed:
                    p = dict(params)
                    q = self._sign(p)
                    url = f"{base}{path}?{q}"
                    res = self.session.request(method, url, timeout=timeout)
                else:
                    url = f"{base}{path}"
                    res = self.session.request(method, url, params=params, timeout=timeout)
                
                if res.status_code == 200:
                    self.active_base_url = base
                    return res.json()
                elif res.status_code in [400, 401, 403]:
                    # Bad request or Auth error (not network error)
                    return {"error": True, "status": res.status_code, "detail": res.json()}
                else:
                    last_error = f"Status {res.status_code}: {res.text[:100]}"
            except Exception as e:
                last_error = str(e)
                continue
                
        return {"error": True, "detail": last_error or "Network unreachable"}

    # ==================== ACCOUNT & USER DATA ====================
    def get_api_permissions(self):
        return self.request("GET", "/sapi/v1/account/apiRestrictions", signed=True)

    def get_account_info(self):
        return self.request("GET", "/api/v3/account", signed=True)

    def get_user_assets(self):
        return self.request("POST", "/sapi/v3/asset/getUserAsset", signed=True)

    def get_deposit_history(self, limit=20):
        return self.request("GET", "/sapi/v1/capital/deposit/hisrec", params={"limit": limit}, signed=True)

    def get_withdraw_history(self, limit=20):
        return self.request("GET", "/sapi/v1/capital/withdraw/history", params={"limit": limit}, signed=True)

    def get_dust_log(self):
        return self.request("GET", "/sapi/v1/asset/dribblet", signed=True)

    def get_open_orders(self, symbol=None):
        p = {"symbol": symbol} if symbol else {}
        return self.request("GET", "/api/v3/openOrders", params=p, signed=True)

    def get_my_trades(self, symbol="BTCUSDT", limit=50):
        return self.request("GET", "/api/v3/myTrades", params={"symbol": symbol, "limit": limit}, signed=True)

    # ==================== PUBLIC MARKET DATA ====================
    def get_ticker_24h(self, symbol=None):
        p = {"symbol": symbol} if symbol else {}
        return self.request("GET", "/api/v3/ticker/24hr", params=p)

    def get_order_book(self, symbol="BTCUSDT", limit=10):
        return self.request("GET", "/api/v3/depth", params={"symbol": symbol, "limit": limit})

    def get_recent_trades(self, symbol="BTCUSDT", limit=20):
        return self.request("GET", "/api/v3/trades", params={"symbol": symbol, "limit": limit})

    def get_klines(self, symbol="BTCUSDT", interval="1h", limit=50):
        return self.request("GET", "/api/v3/klines", params={"symbol": symbol, "interval": interval, "limit": limit})

    def get_system_status(self):
        return self.request("GET", "/sapi/v1/system/status")

