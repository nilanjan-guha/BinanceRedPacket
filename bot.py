import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient, events

from extractor import extract_codes
from claimer import BinanceClaimer

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MainRunner")

# Load environment configuration
load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
CHANNELS_STR = os.getenv("TARGET_CHANNELS", "")
PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR", "./binance_browser_profile")
HEADLESS = os.getenv("HEADLESS", "False").lower() in ("true", "1", "yes")
URL = os.getenv("BINANCE_CRYPTO_BOX_URL", "https://www.binance.com/en/my/wallet/account/payment/cryptobox")
COOLDOWN = float(os.getenv("CLAIM_COOLDOWN_SECONDS", "2"))

# Parse targeted channels/chats if specified
target_chats = [c.strip() for c in CHANNELS_STR.split(",") if c.strip()]

# Cache to avoid submitting the same code twice
seen_codes = set()
# Asynchronous claim queue
claim_queue = asyncio.Queue()

async def worker_claim_loop(claimer: BinanceClaimer):
    """Worker task that consumes detected codes from the queue sequentially."""
    logger.info("Claim queue worker started.")
    while True:
        code = await claim_queue.get()
        try:
            await claimer.claim_code(code)
            await asyncio.sleep(COOLDOWN)
        except Exception as e:
            logger.error(f"Error processing code {code}: {e}")
        finally:
            claim_queue.task_done()

async def main():
    if not API_ID or not API_HASH:
        logger.error(
            "Missing TELEGRAM_API_ID or TELEGRAM_API_HASH. "
            "Please copy .env.example to .env and fill in your credentials."
        )
        sys.exit(1)

    # 1. Start Binance browser instance
    claimer = BinanceClaimer(profile_dir=PROFILE_DIR, target_url=URL, headless=HEADLESS)
    await claimer.start()

    # 2. Launch background claim worker
    worker_task = asyncio.create_task(worker_claim_loop(claimer))

    # 3. Setup Telegram Client
    tg_client = TelegramClient("binance_tg_session", int(API_ID), API_HASH)

    @tg_client.on(events.NewMessage(chats=target_chats if target_chats else None))
    async def incoming_message_handler(event):
        text = event.message.message
        if not text:
            return

        codes = extract_codes(text)
        for code in codes:
            if code not in seen_codes:
                seen_codes.add(code)
                chat_title = getattr(event.chat, 'title', str(event.chat_id))
                logger.info(f"✨ [Telegram - {chat_title}] Found candidate code: {code}")
                await claim_queue.put(code)

    logger.info("Connecting to Telegram...")
    if PHONE:
        await tg_client.start(phone=PHONE)
    else:
        await tg_client.start()

    logger.info("Listening for new messages in Telegram channels...")

    try:
        await tg_client.run_until_disconnected()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown initiated by user.")
    finally:
        worker_task.cancel()
        await claimer.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Terminated.")

