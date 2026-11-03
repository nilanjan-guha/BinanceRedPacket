# Binance Crypto Box / Red Packet Automated Claimer

This project implements an automated listener and claimer for Binance Crypto Box / Red Packet codes shared across Telegram groups and channels.

---

## 🏗 Project Architecture

- **`extractor.py`**: High-accuracy regex extraction for 8-character codes (`BPxxxxxx` or alphanumeric) with heuristic filters to drop false positives (dictionary words, pure text).
- **`claimer.py`**: Playwright browser automation with a persistent user data profile (`binance_browser_profile/`). Keeps your login session, 2FA, and cookies active without needing to re-login every time.
- **`bot.py`**: Telethon real-time Telegram listener connected to an asynchronous FIFO claim queue.
- **`test_extractor.py`**: Verification script to validate code extraction against sample messages.

---

## 🚀 Setup Instructions

### 1. Install Dependencies
Make sure you have Python 3.10+ installed:
```powershell
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Telegram Credentials
1. Visit [https://my.telegram.org](https://my.telegram.org) and log in.
2. Go to **API development tools** and create an app to obtain your `api_id` and `api_hash`.
3. Create a `.env` file from `.env.example`:
```powershell
copy .env.example .env
```
4. Fill in `.env`:
```ini
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+1234567890

# Optional: List specific channels/usernames separated by comma.
# If empty, all chats your Telegram user is in will be monitored.
TARGET_CHANNELS=some_box_channel,crypto_giveaways
```

### 3. First-Time Setup: Log in to Binance
1. Run `python bot.py`.
2. A Chromium browser window will open up and navigate to the Binance Crypto Box redemption page.
3. Log in to your Binance account manually in that opened browser window and complete any 2FA/email prompts.
4. Because `CHROME_PROFILE_DIR=./binance_browser_profile` is configured, your session cookies and login will be saved on your machine. Subsequent runs will remain logged in automatically.

---

## ⚠️ Important Disclaimer
Automated claiming violates Binance terms of service and may trigger Cloudflare bot protections, CAPTCHA challenges, or account restrictions. Use responsibly and at your own risk.

