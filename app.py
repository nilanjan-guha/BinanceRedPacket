import os
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel, Chat
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from extractor import extract_codes
from storage import CodeManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("App")

load_dotenv()
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")

storage = CodeManager("codes_history.json")
app = FastAPI(title="Binance Red Packet Radar")

# Channel filter keywords
TARGET_KEYWORDS = [
    "binance", "red packet", "redpacket", "cryptobox", "crypto box", 
    "box code", "giveaway", "airdrop"
]

# Seed list of top known channels from the web
SEED_CHANNELS = [
    "redpacketdrops",
    "binanceredpacketcoddes",
    "binanceredpacketcodetoday",
    "binanceredpacketcodes17",
    "landofcoins",
    "BinanceBoxDrop",
    "binance_box_codes",
    "cryptobox_binance_free",
    "CryptoBoxesCode"
]

# Search terms to dynamically find brand new public channels on Telegram
DISCOVERY_SEARCH_QUERIES = [
    "Binance Red Packet",
    "Binance Crypto Box",
    "Red Packet Code"
]

monitored_dialog_ids = set()
monitored_dialogs = []  # list of {"id": int, "title": str, "username": str, "joined_at": str}

scan_state = {
    "status": "Initializing",
    "monitored_channels": [],
    "total_monitored": 0,
    "messages_scanned": 0,
    "last_message_channel": "-",
    "last_message_time": "-",
    "last_joined_channel": "-",
    "last_joined_time": "-",
    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

class MarkStatusRequest(BaseModel):
    code: str
    status: str

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/status")
async def get_system_status():
    return scan_state

@app.get("/api/codes")
async def get_codes():
    return storage.get_all()

@app.post("/api/mark")
async def mark_code_status(payload: MarkStatusRequest):
    storage.mark_status(payload.code, payload.status)
    return {"success": True, "code": payload.code, "status": payload.status}

def is_relevant_channel(title: str, username: str = "") -> bool:
    combined = f"{title or ''} {username or ''}".lower()
    return any(keyword in combined for keyword in TARGET_KEYWORDS)

def record_channel(entity, source_note: str = ""):
    cid = getattr(entity, 'id', None)
    if not cid:
        return
    # Telethon channel IDs usually require the -100 prefix or raw id depending on event
    title = getattr(entity, 'title', None) or getattr(entity, 'first_name', '') or str(cid)
    username = getattr(entity, 'username', '') or ''
    now_str = datetime.now().strftime("%H:%M:%S")

    if cid not in monitored_dialog_ids:
        monitored_dialog_ids.add(cid)
        channel_info = {
            "id": cid,
            "title": title,
            "username": f"@{username}" if username else "-",
            "joined_at": now_str
        }
        monitored_dialogs.append(channel_info)
        scan_state["monitored_channels"] = monitored_dialogs
        scan_state["total_monitored"] = len(monitored_dialogs)
        scan_state["last_joined_channel"] = f"{title} (@{username})" if username else title
        scan_state["last_joined_time"] = now_str
        logger.info(f"📌 [NEW CHANNEL ADDED TO SCANNER] {title} (@{username}) {source_note}")

async def initial_load_existing_dialogs(client: TelegramClient):
    """Filter user's existing joined chats for relevant ones."""
    logger.info("Scanning currently joined chats for Binance / Red Packet / Crypto Box...")
    async for dialog in client.iter_dialogs():
        title = dialog.name or ""
        username = getattr(dialog.entity, "username", "") or ""
        if is_relevant_channel(title, username):
            record_channel(dialog.entity, source_note="[Existing Dialog]")

async def join_seed_channels(client: TelegramClient):
    """Joins seed channels from the web."""
    for ch_name in SEED_CHANNELS:
        try:
            entity = await client.get_entity(ch_name)
            await client(JoinChannelRequest(entity))
            record_channel(entity, source_note="[Joined Seed]")
            await asyncio.sleep(1.5)  # Telegram rate limit safety
        except Exception as e:
            logger.debug(f"Could not join seed {ch_name}: {e}")

async def dynamic_channel_discovery_loop(client: TelegramClient):
    """
    Periodically searches Telegram for new public channels matching
    'Binance Red Packet' / 'Crypto Box' and auto-joins them, reporting to UI.
    """
    while True:
        try:
            logger.info("🔎 Searching Telegram global directory for new Binance Red Packet channels...")
            for query in DISCOVERY_SEARCH_QUERIES:
                try:
                    result = await client(SearchRequest(q=query, limit=10))
                    for chat in result.chats:
                        if isinstance(chat, (Channel, Chat)):
                            title = getattr(chat, 'title', '')
                            username = getattr(chat, 'username', '')
                            
                            if is_relevant_channel(title, username) and chat.id not in monitored_dialog_ids:
                                try:
                                    # Join the newly discovered channel
                                    await client(JoinChannelRequest(chat))
                                    record_channel(chat, source_note="[Auto-Discovered & Joined]")
                                    await asyncio.sleep(2)
                                except Exception as join_err:
                                    logger.debug(f"Auto-join failed for {title}: {join_err}")
                except Exception as q_err:
                    logger.debug(f"Query '{query}' search error: {q_err}")

                await asyncio.sleep(3)

        except Exception as loop_err:
            logger.error(f"Discovery loop error: {loop_err}")

        # Re-check and search for new channels every 10 minutes
        await asyncio.sleep(600)

async def start_telegram_listener():
    scan_state["status"] = "Connecting to Telegram..."
    client = TelegramClient("binance_tg_session", int(API_ID), API_HASH)

    if PHONE:
        await client.start(phone=PHONE)
    else:
        await client.start()

    scan_state["status"] = "Discovering & Joining Red Packet Channels..."

    # 1. Add matching channels user is already in
    await initial_load_existing_dialogs(client)

    # 2. Join initial known web channels
    await join_seed_channels(client)

    # 3. Launch background dynamic channel search & auto-join loop
    asyncio.create_task(dynamic_channel_discovery_loop(client))

    scan_state["status"] = "Active (Scanning Messages & Discovering Channels)"

    @client.on(events.NewMessage)
    async def handler(event):
        # Only process if from a channel in our monitored list
        # Check by chat_id or peer_id
        chat_id = event.chat_id
        # Also check channel id without -100 prefix if needed
        is_monitored = (chat_id in monitored_dialog_ids) or (abs(chat_id) in monitored_dialog_ids)

        # If not tracked yet, check if channel title/username is relevant and auto-add on the fly
        if not is_monitored:
            try:
                chat = await event.get_chat()
                title = getattr(chat, 'title', '')
                username = getattr(chat, 'username', '')
                if is_relevant_channel(title, username):
                    record_channel(chat, source_note="[Auto-detected Incoming Message]")
                    is_monitored = True
            except Exception:
                pass

        if not is_monitored:
            return

        chat_title = getattr(event.chat, 'title', str(event.chat_id)) if event.chat else str(event.chat_id)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        scan_state["messages_scanned"] += 1
        scan_state["last_message_channel"] = chat_title
        scan_state["last_message_time"] = now_str

        text = event.message.message
        if not text:
            return

        codes = extract_codes(text)
        for code in codes:
            if not storage.is_known(code):
                logger.info(f"✨ NEW CODE DETECTED: {code} from {chat_title}")
                storage.add_code(code, source=chat_title)

    logger.info("Telegram engine fully started and monitoring!")
    await client.run_until_disconnected()

async def main():
    if not API_ID or not API_HASH:
        logger.error("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in .env")
        sys.exit(1)

    asyncio.create_task(start_telegram_listener())

    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    
    logger.info("=" * 60)
    logger.info("🌐 Red Packet Radar is LIVE at: http://127.0.0.1:8000")
    logger.info("=" * 60)
    
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        scan_state["status"] = "Stopped"
        logger.info("Stopped.")
