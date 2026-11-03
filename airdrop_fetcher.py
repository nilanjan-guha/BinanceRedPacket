import os
import logging
import urllib.request
import json
from typing import List, Dict, Any

logger = logging.getLogger("AirdropFetcher")

# Curated list of verified zero-cost active testnet airdrops
VERIFIED_TESTNETS = [
    {
        "id": "berachain",
        "name": "Berachain Testnet (bArtio)",
        "chain": "Berachain (EVM)",
        "cost": "₹0 (Free Faucet)",
        "reward_potential": "$500 – $2,500+",
        "status": "ACTIVE_TESTNET",
        "category": "Layer 1 / DeFi",
        "action_summary": "Claim free BERA from faucet, swap on BEX, mint HONEY.",
        "faucet_url": "https://bartio.faucet.berachain.com/",
        "guide_url": "https://docs.berachain.com/learn/how-to-connect",
        "verified": True
    },
    {
        "id": "monad",
        "name": "Monad Devnet / Testnet",
        "chain": "Monad EVM",
        "cost": "₹0 (Free Faucet)",
        "reward_potential": "$1,000 – $4,000+",
        "status": "UPCOMING / EARLY",
        "category": "Ultra-Fast EVM Layer 1",
        "action_summary": "Join community Discord, register wallet for early faucet drops.",
        "faucet_url": "https://testnet.monad.xyz/",
        "guide_url": "https://docs.monad.xyz/",
        "verified": True
    },
    {
        "id": "story-protocol",
        "name": "Story Protocol (Iliad Testnet)",
        "chain": "Story EVM",
        "cost": "₹0 (Free Faucet)",
        "reward_potential": "$300 – $1,200+",
        "status": "ACTIVE_TESTNET",
        "category": "IP & AI Layer 1",
        "action_summary": "Claim Iliad IP tokens, register sample IP asset, mint test license.",
        "faucet_url": "https://faucet.story.foundation/",
        "guide_url": "https://docs.story.foundation/",
        "verified": True
    },
    {
        "id": "solana-devnet-quests",
        "name": "Solana Ecosystem Devnet Quests",
        "chain": "Solana Devnet",
        "cost": "₹0 (Free Faucet)",
        "reward_potential": "$100 – $800+",
        "status": "ACTIVE",
        "category": "Solana dApps",
        "action_summary": "Use Devnet SOL to test new DEXes, perpetuals, and NFT mints.",
        "faucet_url": "https://faucet.solana.com/",
        "guide_url": "https://solana.com/developers",
        "verified": True
    },
    {
        "id": "linea-voyage",
        "name": "Linea / Consensys Testnet",
        "chain": "Linea zkEVM",
        "cost": "₹0 (Free Faucet)",
        "reward_potential": "$200 – $1,000+",
        "status": "ONGOING_POINTS",
        "category": "zk-Rollup L2",
        "action_summary": "Complete testnet tasks on Layer3/Galxe for Linea LXP-L.",
        "faucet_url": "https://faucetlink.to/linea-sepolia",
        "guide_url": "https://linea.build/",
        "verified": True
    }
]

class AirdropManager:
    def __init__(self):
        self.cached_airdrops = VERIFIED_TESTNETS

    def get_active_testnets(self) -> List[Dict[str, Any]]:
        return self.cached_airdrops

    def fetch_defillama_protocols(self) -> List[Dict[str, Any]]:
        """Queries DefiLlama public API for unreleased token protocols."""
        url = "https://api.llama.fi/protocols"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    # Filter protocols without a token (airdrop candidates)
                    tokenless = [
                        p for p in data 
                        if not p.get("symbol") or p.get("symbol") == "-"
                    ][:10]
                    return tokenless
        except Exception as e:
            logger.debug(f"DefiLlama fetch fallback: {e}")
        return []
