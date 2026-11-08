import os
import time
import uvicorn
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse
from binance_service import BinanceClient
from kucoin_service import KuCoinClient

app = FastAPI(title="Binance & KuCoin Early-Breakout & Signal Terminal")
binance_client = BinanceClient()
kucoin_client = KuCoinClient()

_cache = {
    "binance_tickers": None,
    "binance_last_fetched": 0,
    "binance_signals": None,
    "binance_last_calc": 0,
    
    "kucoin_tickers": None,
    "kucoin_last_fetched": 0,
    "kucoin_signals": None,
    "kucoin_last_calc": 0,
    
    "active_trade": None,
    "trade_history": []
}

STABLECOINS = {
    'USDCUSDT', 'USD1USDT', 'UUSDT', 'FDUSDUSDT', 'EURUSDT', 'TUSDUSDT', 
    'USDPUSDT', 'BUSDUSDT', 'DAIUSDT', 'AEURUSDT', 'XAUTUSDT', 'PAXGUSDT',
    'USDC-USDT', 'TUSD-USDT', 'DAI-USDT', 'USDD-USDT', 'EUR-USDT'
}

def get_binance_tickers():
    now = time.time()
    if _cache["binance_tickers"] and (now - _cache["binance_last_fetched"]) < 3.0:
        return _cache["binance_tickers"]
    raw = binance_client.get_ticker_24h()
    if isinstance(raw, list):
        _cache["binance_tickers"] = raw
        _cache["binance_last_fetched"] = now
        return raw
    return _cache["binance_tickers"] or []

def get_kucoin_tickers():
    now = time.time()
    if _cache["kucoin_tickers"] and (now - _cache["kucoin_last_fetched"]) < 3.0:
        return _cache["kucoin_tickers"]
    raw = kucoin_client.get_all_tickers()
    if isinstance(raw, list):
        _cache["kucoin_tickers"] = raw
        _cache["kucoin_last_fetched"] = now
        return raw
    return _cache["kucoin_tickers"] or []

def normalize_symbol_for_exchange(symbol: str, exchange: str = "binance") -> str:
    """Ensures KuCoin receives 'BASE-QUOTE' (e.g. TRX-USDT) and Binance receives 'BASEQUOTE' (e.g. TRXUSDT)."""
    s = (symbol or "").strip()
    if exchange == "kucoin":
        if "-" not in s:
            for quote in ["USDT", "USDC", "BTC", "ETH", "EUR", "KCS"]:
                if s.endswith(quote) and len(s) > len(quote):
                    return f"{s[:-len(quote)]}-{quote}"
        return s
    else:
        return s.replace("-", "")

def safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def get_order_flow_metrics(symbol, exchange="binance"):
    """Fetches real-time Bid vs Ask Wall Imbalance and Taker Market Flow"""
    norm_symbol = normalize_symbol_for_exchange(symbol, exchange=exchange)
    try:
        if exchange == "binance":
            depth = binance_client.get_order_book(symbol=norm_symbol, limit=20)
            trades = binance_client.get_recent_trades(symbol=norm_symbol, limit=25)
            bids = sum([safe_float(b[1]) for b in depth.get("bids", []) if len(b) > 1])
            asks = sum([safe_float(a[1]) for a in depth.get("asks", []) if len(a) > 1])
            ratio = round(bids / asks, 2) if asks > 0 else 1.0
            buys = len([t for t in trades if not t.get("isBuyerMaker", False)])
            buy_flow = round((buys / len(trades)) * 100, 1) if trades else 50.0
        else:
            depth = kucoin_client.get_order_book(symbol=norm_symbol)
            trades = kucoin_client.get_recent_trades(symbol=norm_symbol)
            bids = sum([safe_float(b[1]) for b in depth.get("bids", []) if len(b) > 1])
            asks = sum([safe_float(a[1]) for a in depth.get("asks", []) if len(a) > 1])
            ratio = round(bids / asks, 2) if asks > 0 else 1.0
            buys = len([t for t in trades if t.get("side") == "buy"])
            buy_flow = round((buys / len(trades)) * 100, 1) if trades else 50.0

        return {"book_ratio": ratio, "buy_flow": buy_flow, "bid_vol": bids, "ask_vol": asks}
    except Exception:
        return {"book_ratio": 1.0, "buy_flow": 50.0, "bid_vol": 0, "ask_vol": 0}

def calculate_market_engine(tickers, exchange="binance", quote="USDT"):
    """
    Two-Stage Detection:
    1. PRE-BREAKOUT / STEALTH ACCUMULATION (Coins that have NOT moved yet, but heavy buyers/sellers are loading)
    2. ACTIVE TREND SIGNALS (Standard momentum setups)
    """
    analyzed_pre_move = []
    analyzed_standard = []

    for t in tickers:
        try:
            if exchange == "binance":
                symbol = t.get("symbol", "")
                if quote != "ALL" and not symbol.endswith(quote):
                    continue
                if symbol in STABLECOINS:
                    continue
                p = float(t.get("lastPrice", 0))
                chg = float(t.get("priceChangePercent", 0))
                vol = float(t.get("quoteVolume", 0))
                high = float(t.get("highPrice", 0))
                low = float(t.get("lowPrice", 0))
                trades = int(t.get("count", 0))
            else: # kucoin
                symbol = t.get("symbol", "")
                target_suffix = f"-{quote}" if quote != "ALL" else ""
                if target_suffix and not symbol.endswith(target_suffix):
                    continue
                if symbol in STABLECOINS:
                    continue
                p = float(t.get("last", 0))
                chg = float(t.get("changeRate", 0)) * 100
                vol = float(t.get("volValue", 0))
                high = float(t.get("high", 0))
                low = float(t.get("low", 0))
                trades = int(float(t.get("vol", 0)))

            if vol < 250000 or p == 0:
                continue

            span = high - low
            range_pos = ((p - low) / span) if span > 0 else 0.5
            range_pct = ((high - low) / low) * 100 if low > 0 else 100

            # Target levels
            tp_long = round(p * 1.052, 6)
            sl_long = round(p * 0.976, 6)
            tp_short = round(p * 0.948, 6)
            sl_short = round(p * 1.024, 6)

            # ================= CRITERIA: HAS NOT PUMPED / MOVED YET =================
            # - Price hasn't run away: between -3.5% and +3.5%
            # - Tight range compression: daily volatility range <= 6.5% (compression coil)
            # - High liquidity & active order placement
            is_coiling = (-3.5 <= chg <= 3.5) and (range_pct <= 6.5) and (trades > 7000)

            if is_coiling:
                # Pre-move score (Potential explosive breakout)
                pre_score = 70
                pre_checks = [
                    f"Consolidation coil: range compressed at {range_pct:.1f}%",
                    f"Has NOT moved yet (24h change only {chg:+.2f}%)",
                    f"Liquidity ready: ${vol/1e6:.2f}M turnover with {trades:,} orders"
                ]

                analyzed_pre_move.append({
                    "exchange": exchange,
                    "symbol": symbol,
                    "price": p,
                    "change": round(chg, 2),
                    "range_pct": round(range_pct, 1),
                    "volume": vol,
                    "trades": trades,
                    "score": pre_score,
                    "checks": pre_checks,
                    "tp_long": tp_long,
                    "sl_long": sl_long,
                    "tp_short": tp_short,
                    "sl_short": sl_short
                })

            # ================= CRITERIA: GENERAL LONG / SHORT SCORE =================
            long_score = 0
            long_checks = []
            if chg > 5.0:
                long_score += min(chg * 1.5, 30)
                long_checks.append(f"+{chg:.1f}% 24h momentum thrust")
            elif chg > 0:
                long_score += 10
                long_checks.append(f"+{chg:.1f}% positive price trend")

            if range_pos >= 0.70:
                long_score += 26
                long_checks.append("Bullish: Trading at top 30% daily high")
            elif range_pos >= 0.50:
                long_score += 12

            if vol > 3000000:
                long_score += 22
                long_checks.append(f"Institutional liquidity (${vol/1e6:.1f}M)")
            elif vol > 600000:
                long_score += 12
                long_checks.append(f"Solid liquidity (${vol/1e6:.1f}M)")

            if trades > 18000:
                long_score += 15
                long_checks.append("High transaction frequency")
            elif trades > 5000:
                long_score += 8

            long_score = min(max(round(long_score, 1), 0), 100)

            short_score = 0
            short_checks = []
            if chg < -5.0:
                short_score += min(abs(chg) * 1.6, 30)
                short_checks.append(f"{chg:.1f}% 24h severe dump")
            elif chg < 0:
                short_score += 10
                short_checks.append(f"{chg:.1f}% negative price decay")

            if range_pos <= 0.30:
                short_score += 26
                short_checks.append("Bearish: Piercing bottom 30% breakdown")
            elif range_pos <= 0.45:
                short_score += 12

            if vol > 2000000:
                short_score += 22
                short_checks.append(f"Heavy panic dumping turnover (${vol/1e6:.1f}M)")
            elif vol > 400000:
                short_score += 12
                short_checks.append(f"Active liquidation pressure (${vol/1e6:.1f}M)")

            if trades > 15000:
                short_score += 15
                short_checks.append("Aggressive panic sell orders")
            elif trades > 4000:
                short_score += 8

            short_score = min(max(round(short_score, 1), 0), 100)

            analyzed_standard.append({
                "exchange": exchange,
                "symbol": symbol,
                "price": p,
                "change": round(chg, 2),
                "volume": vol,
                "trades": trades,
                "long_score": long_score,
                "long_checks": long_checks,
                "short_score": short_score,
                "short_checks": short_checks,
                "long_tp": tp_long,
                "long_sl": sl_long,
                "short_tp": tp_short,
                "short_sl": sl_short
            })
        except Exception:
            continue

    # Enrich top pre-breakout coins with live Depth Imbalance and Flow
    for coin in analyzed_pre_move[:6]:
        meta = get_order_flow_metrics(coin["symbol"], exchange=exchange)
        ratio = meta["book_ratio"]
        buy_flow = meta["buy_flow"]
        coin["book_ratio"] = ratio
        coin["buy_flow"] = buy_flow

        # Pre-move direction based on order book & flow
        if ratio >= 1.25 or buy_flow >= 55.0:
            coin["pre_direction"] = "PRE-PUMP LONG (BUYERS ACCUMULATING)"
            coin["dir_color"] = "emerald"
            coin["score"] += 15
            coin["checks"].append(f"Heavy Bid Wall Support ({ratio}x more buyers than sellers)")
            coin["checks"].append(f"Buyer Aggression: {buy_flow}% of live orders are Taker Buys")
        elif ratio <= 0.80 or buy_flow <= 42.0:
            coin["pre_direction"] = "PRE-DUMP SHORT (SELLERS DISTRIBUTING)"
            coin["dir_color"] = "rose"
            coin["score"] += 15
            coin["checks"].append(f"Heavy Ask Wall Resistance (Sellers blocking price)")
            coin["checks"].append(f"Seller Aggression: {(100-buy_flow):.1f}% of live orders are Dumping")
        else:
            coin["pre_direction"] = "NEUTRAL COIL (AWAITING TRIGGER)"
            coin["dir_color"] = "yellow"

    top_pre_breakout = sorted(analyzed_pre_move, key=lambda x: x["score"], reverse=True)[:10]
    top_longs = sorted(analyzed_standard, key=lambda x: x["long_score"], reverse=True)[:15]
    top_shorts = sorted(analyzed_standard, key=lambda x: x["short_score"], reverse=True)[:15]

    # Best Early Pick (Highest Probability Coin That Has NOT Pumped Yet)
    best_early_pick = top_pre_breakout[0] if top_pre_breakout else None

    # Overall Best Trade Decision
    best_l = top_longs[0] if top_longs else None
    best_s = top_shorts[0] if top_shorts else None

    if best_early_pick and best_early_pick.get("pre_direction", "").startswith("PRE-PUMP"):
        overall_winner = {
            "exchange": exchange,
            "direction": "LONG (PRE-PUMP EARLY ENTRY)",
            "symbol": best_early_pick["symbol"],
            "score": best_early_pick["score"],
            "price": best_early_pick["price"],
            "change": best_early_pick["change"],
            "reason": f"Coin has NOT moved yet ({best_early_pick['change']:+}% 24h) but Bid Wall is {best_early_pick.get('book_ratio', 1.0)}x heavier with high buyer accumulation",
            "checks": best_early_pick["checks"],
            "tp": best_early_pick["tp_long"],
            "sl": best_early_pick["sl_long"]
        }
    elif best_l and best_s:
        if best_l["long_score"] >= best_s["short_score"]:
            overall_winner = {
                "exchange": exchange,
                "direction": "LONG",
                "symbol": best_l["symbol"],
                "score": best_l["long_score"],
                "price": best_l["price"],
                "change": best_l["change"],
                "reason": f"Long breakout setup ({best_l['long_score']}%) stronger than Short ({best_s['short_score']}%)",
                "checks": best_l["long_checks"],
                "tp": best_l["long_tp"],
                "sl": best_l["long_sl"]
            }
        else:
            overall_winner = {
                "exchange": exchange,
                "direction": "SHORT",
                "symbol": best_s["symbol"],
                "score": best_s["short_score"],
                "price": best_s["price"],
                "change": best_s["change"],
                "reason": f"Short breakdown setup ({best_s['short_score']}%) stronger than Long ({best_l['long_score']}%)",
                "checks": best_s["short_checks"],
                "tp": best_s["short_tp"],
                "sl": best_s["short_sl"]
            }
    else:
        overall_winner = None

    return {
        "exchange": exchange,
        "timestamp": int(time.time()),
        "quote": quote,
        "master_winner": overall_winner,
        "top_pre_breakout": top_pre_breakout,
        "top_longs": top_longs,
        "top_shorts": top_shorts,
        "all_coins": analyzed_standard
    }

def update_active_trade():
    trade = _cache["active_trade"]
    if not trade:
        return None

    symbol = trade["symbol"]
    exchange = trade.get("exchange", "binance")

    current_price = trade["entry_price"]
    try:
        norm_sym = normalize_symbol_for_exchange(symbol, exchange=exchange)
        if exchange == "binance":
            t = binance_client.get_ticker_24h(symbol=norm_sym)
            if t and "lastPrice" in t and t["lastPrice"] is not None:
                current_price = safe_float(t["lastPrice"], current_price)
        else:
            t = kucoin_client.get_ticker_24h(symbol=norm_sym)
            if t and "last" in t and t["last"] is not None:
                current_price = safe_float(t["last"], current_price)
    except Exception:
        pass

    trade["current_price"] = current_price
    entry = trade["entry_price"]
    tp = trade["tp"]
    sl = trade["sl"]
    is_long = "LONG" in trade["direction"]

    if is_long:
        pnl = ((current_price - entry) / entry) * 100
        if current_price >= tp:
            trade["status"] = "PROFIT TARGET HIT (+5.2%)"
            trade["is_closed"] = True
        elif current_price <= sl:
            trade["status"] = "STOP LOSS TRIGGERED (-2.4%)"
            trade["is_closed"] = True
        else:
            trade["status"] = "IN PROGRESS (ACTIVE)"
    else:
        pnl = ((entry - current_price) / entry) * 100
        if current_price <= tp:
            trade["status"] = "PROFIT TARGET HIT (+5.2%)"
            trade["is_closed"] = True
        elif current_price >= sl:
            trade["status"] = "STOP LOSS TRIGGERED (-2.4%)"
            trade["is_closed"] = True
        else:
            trade["status"] = "IN PROGRESS (ACTIVE)"

    trade["pnl_pct"] = round(pnl, 2)
    trade["duration_seconds"] = int(time.time() - trade["started_at"])
    return trade

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    return FileResponse(html_path)

@app.get("/api/market/signals")
async def get_signals_route(exchange: str = "binance", quote: str = "USDT"):
    now = time.time()
    active_trade = update_active_trade()

    if exchange == "kucoin":
        if _cache["kucoin_signals"] and (now - _cache["kucoin_last_calc"]) < 3.0:
            res = dict(_cache["kucoin_signals"])
            res["active_trade"] = active_trade
            return res
        tickers = get_kucoin_tickers()
        result = calculate_market_engine(tickers, exchange="kucoin", quote=quote)
        _cache["kucoin_signals"] = result
        _cache["kucoin_last_calc"] = now
    else:
        if _cache["binance_signals"] and (now - _cache["binance_last_calc"]) < 3.0:
            res = dict(_cache["binance_signals"])
            res["active_trade"] = active_trade
            return res
        tickers = get_binance_tickers()
        result = calculate_market_engine(tickers, exchange="binance", quote=quote)
        _cache["binance_signals"] = result
        _cache["binance_last_calc"] = now

    if not _cache["active_trade"] and result.get("master_winner"):
        w = result["master_winner"]
        _cache["active_trade"] = {
            "id": f"trade_{int(time.time())}",
            "exchange": exchange,
            "direction": w["direction"],
            "symbol": w["symbol"],
            "score": w["score"],
            "entry_price": w["price"],
            "current_price": w["price"],
            "tp": w["tp"],
            "sl": w["sl"],
            "checks": w["checks"],
            "started_at": time.time(),
            "pnl_pct": 0.0,
            "status": "IN PROGRESS (ACTIVE)",
            "is_closed": False
        }
        active_trade = _cache["active_trade"]

    result["active_trade"] = active_trade
    return result

@app.post("/api/trade/lock")
async def lock_trade(symbol: str, direction: str, exchange: str = "binance"):
    is_long = "LONG" in direction.upper()
    norm_sym = normalize_symbol_for_exchange(symbol, exchange=exchange)
    p = 0.0

    if exchange == "kucoin":
        t = kucoin_client.get_ticker_24h(symbol=norm_sym)
        p = safe_float(t.get("last"))
    else:
        t = binance_client.get_ticker_24h(symbol=norm_sym)
        p = safe_float(t.get("lastPrice"))

    if p == 0:
        return {"error": "Price not found"}

    tp = round(p * 1.052, 6) if is_long else round(p * 0.948, 6)
    sl = round(p * 0.976, 6) if is_long else round(p * 1.024, 6)

    _cache["active_trade"] = {
        "id": f"trade_{int(time.time())}",
        "exchange": exchange,
        "direction": direction.upper(),
        "symbol": symbol,
        "score": 85,
        "entry_price": p,
        "current_price": p,
        "tp": tp,
        "sl": sl,
        "checks": [f"Manually locked {direction.upper()} on {exchange.upper()}", "Tracking real-time profit targets (+5.2% TP / -2.4% SL)"],
        "started_at": time.time(),
        "pnl_pct": 0.0,
        "status": "IN PROGRESS (ACTIVE)",
        "is_closed": False
    }
    return _cache["active_trade"]

@app.post("/api/trade/close")
async def close_trade():
    if _cache["active_trade"]:
        c = dict(_cache["active_trade"])
        c["is_closed"] = True
        c["status"] = "CLOSED BY USER"
        _cache["trade_history"].append(c)
        _cache["active_trade"] = None
    return {"status": "cleared"}

@app.get("/api/orderbook")
async def get_orderbook(symbol: str, exchange: str = "binance", limit: int = 12):
    norm_sym = normalize_symbol_for_exchange(symbol, exchange=exchange)
    if exchange == "kucoin":
        res = kucoin_client.get_order_book(symbol=norm_sym) or {}
        bids = res.get("bids") or []
        asks = res.get("asks") or []
        return {
            "bids": bids[:limit] if isinstance(bids, list) else [],
            "asks": asks[:limit] if isinstance(asks, list) else []
        }
    res = binance_client.get_order_book(symbol=norm_sym, limit=limit) or {}
    bids = res.get("bids") or []
    asks = res.get("asks") or []
    return {
        "bids": bids[:limit] if isinstance(bids, list) else [],
        "asks": asks[:limit] if isinstance(asks, list) else []
    }

@app.get("/api/ticker")
async def get_ticker(symbol: str, exchange: str = "binance"):
    norm_sym = normalize_symbol_for_exchange(symbol, exchange=exchange)
    if exchange == "kucoin":
        t = kucoin_client.get_ticker_24h(symbol=norm_sym)
        chg_rate = safe_float(t.get("changeRate"), 0.0)
        return {
            "symbol": symbol,
            "lastPrice": str(safe_float(t.get("last"), 0.0)),
            "priceChangePercent": str(round(chg_rate * 100, 2)),
            "quoteVolume": str(safe_float(t.get("volValue"), 0.0)),
            "highPrice": str(safe_float(t.get("high"), 0.0)),
            "lowPrice": str(safe_float(t.get("low"), 0.0))
        }
    return binance_client.get_ticker_24h(symbol=norm_sym)

@app.get("/api/trades")
async def get_trades(symbol: str, exchange: str = "binance", limit: int = 10):
    norm_sym = normalize_symbol_for_exchange(symbol, exchange=exchange)
    if exchange == "kucoin":
        raw = kucoin_client.get_recent_trades(symbol=norm_sym)
        parsed = []
        for r in raw[:limit]:
            parsed.append({
                "price": r.get("price"),
                "qty": r.get("size"),
                "time": int(safe_float(r.get("time"), 0)) // 1000000,
                "isBuyerMaker": (r.get("side") == "sell")
            })
        return parsed
    return binance_client.get_recent_trades(symbol=norm_sym, limit=limit)

@app.get("/api/confluence/{symbol}")
async def get_confluence(symbol: str, exchange: str = "binance"):
    return get_order_flow_metrics(symbol, exchange=exchange)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
