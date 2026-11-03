import os
import json
import logging
import urllib.request
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OnChainVerifier")

load_dotenv()

WALLETS = {
    "PHANTOM_SOL": os.getenv("PHANTOM_SOL_WALLET", "c4Nc4Sihyi9Gt16mGAo6HJBVBYTmAZcsBqGjHMVAL8a"),
    "TRUST_SOL": os.getenv("TRUST_SOL_WALLET", "FPYvcBK6j5z6diQhT6KaFEX5AVP7kbEiEQjiM3bvbEZP"),
    "TRUST_EVM": os.getenv("TRUST_ETH_WALLET", "0x2De39611abB941664027a3a0cb5cD7228e9c9f8d"),
    "PHANTOM_EVM": os.getenv("PHANTOM_ETH_WALLET", "0xd1a9b8b92c101ae55c6e5d4d98b30a7f97b8ef57"),
    "TRUST_TRON": os.getenv("TRUST_TRON_WALLET", "TF2w8pfN2QfXP31ZG2Ju5K4fXVEtA8X33u"),
    "TRUST_BTC": os.getenv("TRUST_BTC_WALLET", "bc1qdfe99xlw7mkjznh0zpwvnmwq7nlghlzd3uz939")
}

HARVEST_LOG_FILE = "harvest_history.json"

class AutoHarvester:
    """
    STRICT ON-CHAIN AUDITOR:
    - Only logs when a real change happens (e.g. balance changes or new tip arrived).
    - NEVER spams duplicate logs every cycle.
    """
    def __init__(self, log_path=HARVEST_LOG_FILE):
        self.log_path = log_path
        self.history = self._load()
        # Track last known balances to prevent spamming duplicate logs
        self.last_balances = {}

    def _load(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save(self):
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Save error: {e}")

    def add_verified_record(self, network: str, source: str, target_wallet: str, status: str, detail: str, reason: str):
        record = {
            "id": len(self.history) + 1,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "network": network,
            "wallet": target_wallet,
            "status": status,
            "detail": detail,
            "reason": reason
        }
        self.history.insert(0, record)
        if len(self.history) > 100:
            self.history = self.history[:100]
        self._save()
        return record

    def get_solana_balance(self, wallet_address: str, endpoint: str = "https://api.devnet.solana.com") -> float:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet_address]
        }
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode('utf-8'))
                lamports = data.get("result", {}).get("value", 0)
                return round(lamports / 1_000_000_000, 4)
        except Exception as e:
            logger.debug(f"Solana balance check error: {e}")
            return 0.0

    def get_evm_balance(self, wallet_address: str) -> float:
        alchemy_key = os.getenv("ALCHEMY_API_KEY", "")
        if not alchemy_key:
            return 0.0
        url = f"https://eth-sepolia.g.alchemy.com/v2/{alchemy_key}"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getBalance",
            "params": [wallet_address, "latest"]
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode('utf-8'))
                hex_wei = data.get("result", "0x0")
                wei = int(hex_wei, 16)
                return round(wei / (10**18), 4)
        except Exception as e:
            logger.debug(f"EVM balance check error: {e}")
            return 0.0

    async def run_faucet_auto_cycle(self):
        """Only logs when a real balance change or new transaction is detected."""
        # 1. Audit Phantom Solana Devnet
        p_sol = self.get_solana_balance(WALLETS["PHANTOM_SOL"])
        prev_p_sol = self.last_balances.get("PHANTOM_SOL")

        if prev_p_sol != p_sol and p_sol > 0:
            self.last_balances["PHANTOM_SOL"] = p_sol
            self.add_verified_record(
                network="Solana Devnet",
                source="Solana RPC Validator",
                target_wallet=WALLETS["PHANTOM_SOL"],
                status="CLAIMED",
                detail=f"Real On-Chain Balance: {p_sol} SOL",
                reason=f"Current confirmed balance in Phantom wallet (Verified on-chain)"
            )

        # 2. Audit Trust Solana
        t_sol = self.get_solana_balance(WALLETS["TRUST_SOL"])
        prev_t_sol = self.last_balances.get("TRUST_SOL")
        if prev_t_sol != t_sol and t_sol > 0:
            self.last_balances["TRUST_SOL"] = t_sol
            self.add_verified_record(
                network="Solana Devnet",
                source="Solana RPC Validator",
                target_wallet=WALLETS["TRUST_SOL"],
                status="CLAIMED",
                detail=f"Real On-Chain Balance: {t_sol} SOL",
                reason=f"New confirmed funds received in Trust Solana wallet"
            )

        # 3. Audit Trust EVM Sepolia
        evm_bal = self.get_evm_balance(WALLETS["TRUST_EVM"])
        prev_evm = self.last_balances.get("TRUST_EVM")
        if prev_evm != evm_bal and evm_bal > 0:
            self.last_balances["TRUST_EVM"] = evm_bal
            self.add_verified_record(
                network="Ethereum Sepolia",
                source="Alchemy RPC Node",
                target_wallet=WALLETS["TRUST_EVM"],
                status="CLAIMED",
                detail=f"Real On-Chain Balance: {evm_bal} SepoliaETH",
                reason="New confirmed balance detected in Trust EVM wallet via Alchemy"
            )
