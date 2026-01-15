#!/usr/bin/env python3

import sqlite3
import json
from datetime import datetime
import time

# =====================================================
# CONFIG
# =====================================================

TICK_DB = "tick_json_data.db"
CANDLE_DB = "minute_candles.db"

# =====================================================
# INPUT DB
# =====================================================

tick_conn = sqlite3.connect(TICK_DB)
tick_cur = tick_conn.cursor()

# =====================================================
# OUTPUT DB
# =====================================================

candle_conn = sqlite3.connect(CANDLE_DB)
candle_cur = candle_conn.cursor()

candle_cur.execute("""
CREATE TABLE IF NOT EXISTS candles_1m (
    time_minute TEXT,
    instrument_token INTEGER,
    symbol TEXT,

    open REAL,
    high REAL,
    low REAL,
    close REAL,

    volume INTEGER,
    oi_change INTEGER,

    bid_qty INTEGER,
    ask_qty INTEGER,
    bid_ask_ratio REAL,

    bid_orders INTEGER,
    ask_orders INTEGER,
    order_imbalance INTEGER
)
""")

candle_cur.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_candle
ON candles_1m(time_minute, instrument_token)
""")

candle_conn.commit()

# =====================================================
# HELPERS
# =====================================================

def minute_floor(ts_str):
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    return dt.replace(second=0).strftime("%Y-%m-%d %H:%M:00")

# =====================================================
# MAIN LOOP
# =====================================================

print("🚀 1-Minute Candle Builder (with ORDER data) started")

last_processed_id = 0

while True:
    tick_cur.execute("""
        SELECT id, ts_ist, instrument_token, symbol, tick_json
        FROM ticks_json
        WHERE id > ?
        ORDER BY id ASC
    """, (last_processed_id,))

    rows = tick_cur.fetchall()
    if not rows:
        time.sleep(1)
        continue

    bucket = {}

    for row in rows:
        row_id, ts, token, symbol, tick_json = row
        last_processed_id = row_id

        minute_ts = minute_floor(ts)
        tick = json.loads(tick_json)

        price = tick.get("lp")
        oi = tick.get("oi") or 0
        vol = tick.get("vol") or 0

        bids = tick.get("bid", [])
        asks = tick.get("ask", [])

        bid_qty = sum(b.get("quantity", 0) for b in bids)
        ask_qty = sum(a.get("quantity", 0) for a in asks)

        bid_orders = sum(b.get("orders", 0) for b in bids)
        ask_orders = sum(a.get("orders", 0) for a in asks)

        ratio = (bid_qty / ask_qty) if ask_qty > 0 else 0

        key = (minute_ts, token)

        if key not in bucket:
            bucket[key] = {
                "symbol": symbol,
                "open": price,
                "high": price,
                "low": price,
                "close": price,

                "first_oi": oi,
                "last_oi": oi,

                "volume": vol,

                "bid_qty": bid_qty,
                "ask_qty": ask_qty,
                "ratio": ratio,

                "bid_orders": bid_orders,
                "ask_orders": ask_orders
            }
        else:
            b = bucket[key]

            b["high"] = max(b["high"], price)
            b["low"] = min(b["low"], price)
            b["close"] = price

            b["last_oi"] = oi
            b["volume"] += vol

            # update depth snapshot (latest tick of minute)
            b["bid_qty"] = bid_qty
            b["ask_qty"] = ask_qty
            b["ratio"] = ratio
            b["bid_orders"] = bid_orders
            b["ask_orders"] = ask_orders

    # INSERT CANDLES
    for (minute_ts, token), d in bucket.items():
        oi_change = d["last_oi"] - d["first_oi"]
        order_imbalance = d["bid_orders"] - d["ask_orders"]

        candle_cur.execute("""
            INSERT OR IGNORE INTO candles_1m
            (time_minute, instrument_token, symbol,
             open, high, low, close,
             volume, oi_change,
             bid_qty, ask_qty, bid_ask_ratio,
             bid_orders, ask_orders, order_imbalance)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            minute_ts, token, d["symbol"],
            d["open"], d["high"], d["low"], d["close"],
            d["volume"], oi_change,
            d["bid_qty"], d["ask_qty"], d["ratio"],
            d["bid_orders"], d["ask_orders"], order_imbalance
        ))

    candle_conn.commit()
