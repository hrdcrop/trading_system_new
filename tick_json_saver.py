#!/usr/bin/env python3

from kiteconnect import KiteTicker, KiteConnect
import sqlite3
import json
from datetime import datetime
import pytz
import signal
import sys

# =====================================================
# CONFIG
# =====================================================

API_KEY = open("api_key.txt").read().strip()
ACCESS_TOKEN = open("access_token.txt").read().strip()

DB_NAME = "tick_json_data.db"
IST = pytz.timezone("Asia/Kolkata")

# ---- ACTIVE TOKENS (UNCHANGED – 19 TOKENS) ----
TOKENS = {
    12601346: "BANKNIFTY",
    12602626: "NIFTY",

    341249: "HDFCBANK",
    1270529: "ICICIBANK",
    779521: "SBIN",
    492033: "KOTAKBANK",
    1510401: "AXISBANK",
    1346049: "INDUSINDBK",

    738561: "RELIANCE",
    2714625: "BHARTIARTL",
    2953217: "TCS",
    408065: "INFY",

    12601602: "FINNIFTY",
    264969: "INDIA_VIX",

    12622082: "BAJFINANCE",
    12621826: "BAJAJFINSV",
    12804354: "SHRIRAMFIN",
    12706818: "MUTHOOTFIN",
    12628994: "CHOLAFIN"
}

# =====================================================
# DATABASE SETUP
# =====================================================

conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS ticks_json (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ist TEXT NOT NULL,
    instrument_token INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    tick_json TEXT NOT NULL
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_ticks_time ON ticks_json(ts_ist)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_ticks_token ON ticks_json(instrument_token)")
conn.commit()

# =====================================================
# KITE SETUP
# =====================================================

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

kws = KiteTicker(API_KEY, ACCESS_TOKEN)

# =====================================================
# SAFE EXIT HANDLER
# =====================================================

def shutdown(sig, frame):
    print("\n🛑 Shutting down safely...")
    try:
        conn.commit()
        conn.close()
    except:
        pass
    try:
        kws.close()
    except:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# =====================================================
# TICK HANDLER
# =====================================================

def on_ticks(ws, ticks):
    ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    rows = []

    for t in ticks:
        token = t.get("instrument_token")
        if token not in TOKENS:
            continue

        depth = t.get("depth", {})

        # ---- FILTERED + 5 LEVEL DEPTH JSON ----
        filtered_tick = {
            "lp": t.get("last_price"),
            "oi": t.get("oi"),
            "vol": t.get("volume"),

            "bid": depth.get("buy", [])[:5],
            "ask": depth.get("sell", [])[:5]
        }

        rows.append((
            ts,
            token,
            TOKENS[token],
            json.dumps(filtered_tick, separators=(",", ":"))
        ))

    if rows:
        cur.executemany(
            "INSERT INTO ticks_json (ts_ist, instrument_token, symbol, tick_json) VALUES (?,?,?,?)",
            rows
        )
        conn.commit()

def on_connect(ws, response):
    ws.subscribe(list(TOKENS.keys()))
    ws.set_mode(ws.MODE_FULL, list(TOKENS.keys()))
    print(f"✅ Connected | Subscribed to {len(TOKENS)} tokens")

def on_close(ws, code, reason):
    print("❌ WebSocket closed:", reason)

def on_error(ws, code, reason):
    print("⚠️ WebSocket error:", reason)

# =====================================================
# START
# =====================================================

kws.on_ticks = on_ticks
kws.on_connect = on_connect
kws.on_close = on_close
kws.on_error = on_error

print("🚀 Tick JSON saver started")
print("📦 DB:", DB_NAME)
print("📊 Tokens:", len(TOKENS))
print("🧠 Mode: FULL (5-level depth)")

kws.connect(threaded=False)
