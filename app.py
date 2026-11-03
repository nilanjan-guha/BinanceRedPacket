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
from auto_harvester import AutoHarvester
from telegram_tipper import TelegramTipClaimer
from web_scraper import WebRedPacketScraper
from campaign_radar import BigPrizeRadar
from binance_client import BinanceOfficialClient
from bybit_client import BybitOfficialClient

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
harvester = AutoHarvester("harvest_history.json")
tipper = TelegramTipClaimer("harvest_history.json")
web_scraper = WebRedPacketScraper(storage)
campaign_radar = BigPrizeRadar()
binance_api = BinanceOfficialClient()
bybit_api = BybitOfficialClient()
app = FastAPI(title="Verified Crypto Radar & Multi-Exchange Hub")

TARGET_KEYWORDS = [
    "binance", "red packet", "redpacket", "cryptobox", "crypto box", 
    "box code", "giveaway", "airdrop", "faucet", "drop"
]

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

DISCOVERY_SEARCH_QUERIES = [
    "Binance Red Packet",
    "Binance Crypto Box",
    "Crypto Box Code",
    "Crypto Airdrop"
]

monitored_dialog_ids = set()
monitored_dialogs = []

scan_state = {
    "status": "Initializing",
    "monitored_channels": [],
    "total_monitored": 0,
    "messages_scanned": 0,
    "last_message_channel": "-",
    "last_message_time": "-",
    "last_joined_channel": "-",
    "last_joined_time": "-",
    "harvest_status": "Idle",
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

@app.get("/api/harvest")
async def get_harvest_records():
    return harvester.history

@app.get("/api/campaigns")
async def get_high_value_campaigns():
    return campaign_radar.scan_all_high_value_campaigns()

@app.get("/api/binance/status")
async def get_binance_account():
    return {
        "status": binance_api.get_account_status(),
        "funding_assets": binance_api.get_funding_wallet_balance()
    }

@app.get("/api/bybit/status")
async def get_bybit_account():
    return {
        "status": bybit_api.get_account_status(),
        "assets": bybit_api.get_wallet_balances()
    }

@app.post("/api/trigger-harvest")
async def trigger_harvest_now():
    logger.info("Real balance verification triggered!")
    asyncio.create_task(harvester.run_faucet_auto_cycle())
    return {"status": "triggered"}

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
        logger.info(f"📌 [NEW CHANNEL ADDED] {title} (@{username}) {source_note}")

async def initial_load_existing_dialogs(client: TelegramClient):
    async for dialog in client.iter_dialogs():
        title = dialog.name or ""
        username = getattr(dialog.entity, "username", "") or ""
        if is_relevant_channel(title, username):
            record_channel(dialog.entity, source_note="[Existing Dialog]")

async def join_seed_channels(client: TelegramClient):
    for ch_name in SEED_CHANNELS:
        try:
            entity = await client.get_entity(ch_name)
            await client(JoinChannelRequest(entity))
            record_channel(entity, source_note="[Joined Seed]")
            await asyncio.sleep(1.5)
        except Exception as e:
            logger.debug(f"Could not join seed {ch_name}: {e}")

async def dynamic_channel_discovery_loop(client: TelegramClient):
    while True:
        try:
            for query in DISCOVERY_SEARCH_QUERIES:
                try:
                    result = await client(SearchRequest(q=query, limit=10))
                    for chat in result.chats:
                        if isinstance(chat, (Channel, Chat)):
                            title = getattr(chat, 'title', '')
                            username = getattr(chat, 'username', '')
                            if is_relevant_channel(title, username) and chat.id not in monitored_dialog_ids:
                                try:
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
        await asyncio.sleep(600)

async def recurring_auto_harvest_loop():
    """Real on-chain balance audit & web code scraping runs continuously."""
    cycle = 0
    while True:
        try:
            cycle += 1
            scan_state["harvest_status"] = "Verifying On-Chain Ledgers & Scraping Web Codes..."
            
            # 1. On-Chain real balance verification
            await harvester.run_faucet_auto_cycle()

            # 2. Web scraper: crawls external web sources for Binance codes every 2 minutes
            if cycle % 2 == 0:
                web_scraper.harvest_web_codes()

            scan_state["harvest_status"] = "On-Chain Audit & Web Radar Active"
        except Exception as e:
            logger.error(f"Audit loop error: {e}")
            scan_state["harvest_status"] = f"Audit Error: {e}"
        await asyncio.sleep(30)

async def start_telegram_listener():
    scan_state["status"] = "Connecting to Telegram..."
    client = TelegramClient("binance_tg_session", int(API_ID), API_HASH)

    if PHONE:
        await client.start(phone=PHONE)
    else:
        await client.start()

    scan_state["status"] = "Discovering & Joining Channels..."

    await initial_load_existing_dialogs(client)
    await join_seed_channels(client)
    asyncio.create_task(dynamic_channel_discovery_loop(client))
    asyncio.create_task(recurring_auto_harvest_loop())

    scan_state["status"] = "Live Telegram Drops & On-Chain Audit Active"

    @client.on(events.NewMessage)
    async def handler(event):
        # 1. Real Telegram tip button claimer
        if event.message.buttons:
            await tipper.handle_message_buttons(event, harvester)

        chat_id = event.chat_id
        is_monitored = (chat_id in monitored_dialog_ids) or (abs(chat_id) in monitored_dialog_ids)

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

    logger.info("Real Telegram engine running!")
    await client.run_until_disconnected()

async def main():
    if not API_ID or not API_HASH:
        logger.error("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in .env")
        sys.exit(1)

    asyncio.create_task(start_telegram_listener())

    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    
    logger.info("=" * 60)
    logger.info("🌐 100% REAL Crypto Radar is LIVE at: http://127.0.0.1:8000")
    logger.info("=" * 60)
    
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        scan_state["status"] = "Stopped"
        logger.info("Stopped.")
