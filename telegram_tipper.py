import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("TipClaimer")

class TelegramTipClaimer:
    """
    Automated claimer for Telegram tipping bots:
    - Cwallet / CCPayment (@cwallet_bot)
    - Tip.cc (@tipcoin_bot / Tip.cc)
    Auto-detects inline claim buttons in airdrop messages and auto-triggers callback clicks.
    """
    def __init__(self, storage_path="harvest_history.json"):
        self.storage_path = storage_path
        self.known_tip_bots = ["cwallet", "cwallet_bot", "tipcc", "tipcoin_bot", "faucetpay_bot"]

    def is_tip_drop(self, message_text: str, sender_username: str = "") -> bool:
        combined = f"{message_text or ''} {sender_username or ''}".lower()
        keywords = ["airdrop", "giveaway", "grab", "claim", "tip.cc", "cwallet", "box drop"]
        return any(k in combined for k in keywords)

    async def handle_message_buttons(self, event, auto_harvester):
        """
        If the message contains an inline claim button (e.g. 'Claim 0.05 USDT'),
        this automatically clicks it within milliseconds.
        """
        message = event.message
        if not message.buttons:
            return False

        chat_title = getattr(event.chat, 'title', str(event.chat_id)) if event.chat else str(event.chat_id)

        for row in message.buttons:
            for btn in row:
                btn_text = btn.text.lower()
                # Look for claim triggers
                if any(trigger in btn_text for trigger in ["claim", "grab", "receive", "take", "open"]):
                    try:
                        logger.info(f"⚡ [AUTO-TIPPER] Found claimable button: '{btn.text}' in {chat_title}")
                        # Auto-click the button on Telegram
                        await btn.click()
                        
                        auto_harvester.add_log(
                            source=f"Telegram Tipper ({chat_title})",
                            target_wallet=os.getenv("TRUST_ETH_WALLET", "0x2De3...9f8d"),
                            network="USDT / BSC / Tron",
                            status="CLAIMED",
                            detail=f"Auto-clicked inline tip button: '{btn.text}'",
                            reason="Instant real-crypto tipping drop claimed via Telegram callback"
                        )
                        return True
                    except Exception as e:
                        logger.debug(f"Button click error: {e}")
        return False
