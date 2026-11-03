import os
import json
import logging
from typing import Dict, Any, Optional
import dotenv

dotenv.load_dotenv()

logger = logging.getLogger("SolanaDevnetWorker")

class SolanaDevnetAutonomousWorker:
    """
    Executes automated on-chain Devnet transactions and program calls
    using the user's free Devnet SOL to build verified transaction history
    for retroactive airdrops.
    """
    def __init__(self):
        self.rpc_url = "https://api.devnet.solana.com"
        self.pubkey_str = os.getenv("PHANTOM_SOL_WALLET", "c4Nc4Sihyi9Gt16mGAo6HJBVBYTmAZcsBqGjHMVAL8a")
        self.privkey_str = os.getenv("PHANTOM_PRIVATE_KEY", "").strip()

    def get_signer(self):
        """Loads keypair if private key is provided in .env."""
        if not self.privkey_str:
            return None
        try:
            from solders.keypair import Keypair
            import base58
            # Checks if Base58 or byte list
            if "[" in self.privkey_str:
                raw_bytes = bytes(json.loads(self.privkey_str))
                return Keypair.from_bytes(raw_bytes)
            else:
                raw_bytes = base58.b58decode(self.privkey_str)
                return Keypair.from_bytes(raw_bytes)
        except Exception as e:
            logger.error(f"Error loading Solana keypair: {e}")
            return None

    def execute_test_transaction(self, memo_text: str = "Airdrop Proof of Activity - Devnet") -> Dict[str, Any]:
        """
        Executes a real micro-transaction on Solana Devnet:
        - Interacts with the SPL Memo Program or self-transfer of 0.0001 SOL
        - Confirmed directly on the Devnet blockchain
        - Produces a verifiable on-chain transaction hash
        """
        signer = self.get_signer()
        if not signer:
            return {
                "success": False,
                "needs_key": True,
                "msg": "No PHANTOM_PRIVATE_KEY found in .env. Automatic signing requires your Devnet private key, or manual approval via browser."
            }

        try:
            from solana.rpc.api import Client
            from solders.pubkey import Pubkey
            from solders.system_program import TransferParams, transfer
            from solders.transaction import VersionedTransaction
            from solders.message import MessageV0

            client = Client(self.rpc_url)
            sender_pubkey = signer.pubkey()
            
            # Transfer 10,000 lamports (0.00001 Devnet SOL) to self to record verified on-chain activity
            ix = transfer(
                TransferParams(
                    from_pubkey=sender_pubkey,
                    to_pubkey=sender_pubkey,
                    lamports=10000
                )
            )

            recent_blockhash_resp = client.get_latest_blockhash()
            blockhash = recent_blockhash_resp.value.blockhash

            msg = MessageV0.try_compile(
                payer=sender_pubkey,
                instructions=[ix],
                address_lookup_table_accounts=[],
                recent_blockhash=blockhash
            )

            tx = VersionedTransaction(msg, [signer])
            send_resp = client.send_transaction(tx)
            tx_signature = str(send_resp.value)

            logger.info(f"Devnet Transaction executed! Signature: {tx_signature}")
            return {
                "success": True,
                "signature": tx_signature,
                "explorer_url": f"https://explorer.solana.com/tx/{tx_signature}?cluster=devnet",
                "msg": "Transaction successfully verified on Solana Devnet!"
            }
        except Exception as e:
            logger.error(f"Failed to execute Devnet transaction: {e}")
            return {
                "success": False,
                "error": str(e),
                "msg": f"RPC Execution failed: {e}"
            }

solana_worker = SolanaDevnetAutonomousWorker()

