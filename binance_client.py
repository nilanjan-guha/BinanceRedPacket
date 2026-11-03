import os
import time
import hmac
import hashlib
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List

logger = logging.getLogger("BinanceClient")

class BinanceOfficialClient:
    """
    Authenticated Binance Client using HMAC-SHA256:
    - Queries official Binance Pay & Funding Wallet balances in real-time
    - Monitors official campaign distributions and announcements
    """
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        self.base_url = "https://api.binance.com"

    def _sign_query(self, params: Dict[str, Any]) -> str:
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def get_funding_wallet_balance(self) -> List[Dict[str, Any]]:
        """Queries the official Funding Wallet (where Red Packet / Crypto Box funds land)."""
        if not self.api_key or not self.api_secret:
            return []

        endpoint = "/sapi/v1/asset/get-funding-asset"
        params = {"timestamp": int(time.time() * 1000), "recvWindow": 5000}
        signed_qs = self._sign_query(params)
        url = f"{self.base_url}{endpoint}?{signed_qs}"

        try:
            req = urllib.request.Request(
                url,
                headers={"X-MBX-APIKEY": self.api_key, "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                # Filter for non-zero assets
                non_zero = [
                    a for a in data 
                    if float(a.get("free", 0)) > 0 or float(a.get("freeze", 0)) > 0
                ]
                return non_zero
        except Exception as e:
            logger.debug(f"Funding wallet query: {e}")
            return []

    def get_account_status(self) -> Dict[str, Any]:
        """Verifies API key validity and account status."""
        if not self.api_key or not self.api_secret:
            return {"connected": False, "reason": "No API keys configured"}

        endpoint = "/api/v3/account"
        params = {"timestamp": int(time.time() * 1000), "recvWindow": 5000}
        signed_qs = self._sign_query(params)
        url = f"{self.base_url}{endpoint}?{signed_qs}"

        try:
            req = urllib.request.Request(
                url,
                headers={"X-MBX-APIKEY": self.api_key, "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return {
                    "connected": True,
                    "accountType": data.get("accountType", "SPOT"),
                    "canTrade": data.get("canTrade", False),
                    "canWithdraw": data.get("canWithdraw", False),
                    "canDeposit": data.get("canDeposit", False)
                }
        except Exception as e:
            return {"connected": False, "reason": str(e)}

