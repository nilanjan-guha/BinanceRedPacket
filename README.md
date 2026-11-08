# Binance & KuCoin Live Signal Scanner & Market Confluence Engine

A real-time crypto scanner and pair trading dashboard powered by FastAPI, Binance, and KuCoin APIs.

## Features
- **Dual Exchange Support**: Toggle between Binance and KuCoin live data.
- **Pre-Breakout Coiling Scanner**: Detects stealth compression setups before high-volatility moves using Level 2 depth imbalances (bid/ask walls) and taker flow.
- **Top Long & Short Rankings**: Sorted high-to-low with target TP (+5.2%) and SL (-2.4%) levels.
- **Order Flow & Depth Inspector**: Real-time order book and executed taker trade feed.
- **Active Trade Tracker**: Locks and persists trade entry price, PnL, and targets across scans.

## Setup & Running

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment** (Optional for private endpoints):
   ```bash
   copy .env.example .env
   ```

3. **Start the Dashboard**:
   ```bash
   python -m uvicorn app:app --host 127.0.0.1 --port 8000
   ```
   Open `http://127.0.0.1:8000` in your browser.
