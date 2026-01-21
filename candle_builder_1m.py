#!/usr/bin/env python3
"""
1-Minute Candle Builder - DAEMON MODE
======================================
Continuously processes tick data into enriched 1-minute candles
Runs every 10 seconds to catch new complete minutes
All timestamps are in IST (Asia/Kolkata)
"""

import sqlite3
import json
import time
import signal
import sys
from datetime import datetime
from collections import defaultdict
import pytz

# ============================================================================
# CONFIGURATION
# ============================================================================

# IST timezone object for all datetime operations
IST = pytz.timezone('Asia/Kolkata')

SOURCE_DB = "tick_json_data.db"
OUTPUT_DB = "market_data.db"
PROCESSING_INTERVAL = 10  # seconds between processing cycles

# Optional: Filter for specific instruments
ALLOWED_TOKENS = None  # Set to {12601346, 12602626} for BANKNIFTY/NIFTY only

# Bias classification thresholds
BUYER_THRESHOLD = 1.2
SELLER_THRESHOLD = 0.8

# Priority weights for depth levels
DEPTH_WEIGHTS = [1.0, 0.8, 0.6, 0.4, 0.2]

# Graceful shutdown flag
shutdown_requested = False

# ============================================================================
# TIMEZONE HELPER
# ============================================================================

def now_ist():
    """Get current datetime in IST timezone"""
    return datetime.now(IST)

def now_ist_str(fmt="%H:%M:%S"):
    """Get current IST time as formatted string"""
    return now_ist().strftime(fmt)

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    print(f"\n🛑 Received signal {signum}, initiating graceful shutdown... [{now_ist_str()}]")
    shutdown_requested = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_output_db():
    """Initialize output database with production schema"""
    conn = sqlite3.connect(OUTPUT_DB)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS minute_candles (
            instrument_token INTEGER NOT NULL,
            time_minute TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            total_bid_qty INTEGER,
            total_ask_qty INTEGER,
            bid_ask_ratio REAL,
            order_imbalance INTEGER,
            bid_ask_bias TEXT,
            weighted_bid_qty REAL,
            weighted_ask_qty REAL,
            weighted_bid_ask_ratio REAL,
            weighted_order_imbalance REAL,
            weighted_bias TEXT,
            PRIMARY KEY (instrument_token, time_minute)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_time_minute
        ON minute_candles(time_minute)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_instrument
        ON minute_candles(instrument_token)
    """)

    conn.commit()
    conn.close()

def parse_ist_minute(ts_ist_str):
    """Extract IST minute bucket from timestamp string"""
    dt = datetime.strptime(ts_ist_str, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d %H:%M")

def compute_depth_metrics(depth_array, weights):
    """Compute total and priority-weighted quantities from depth array"""
    if not depth_array or not isinstance(depth_array, list):
        return 0, 0.0

    total_qty = 0
    weighted_qty = 0.0

    for i, level in enumerate(depth_array):
        if not isinstance(level, dict):
            continue
        qty = level.get('quantity', 0)
        total_qty += qty
        if i < len(weights):
            weighted_qty += qty * weights[i]

    return total_qty, weighted_qty

def extract_last_tick_depth(tick_json_str):
    """Extract depth metrics from last tick snapshot"""
    try:
        tick_data = json.loads(tick_json_str)
        bid_depth = tick_data.get('bid', [])
        ask_depth = tick_data.get('ask', [])

        total_bid_qty, weighted_bid_qty = compute_depth_metrics(bid_depth, DEPTH_WEIGHTS)
        total_ask_qty, weighted_ask_qty = compute_depth_metrics(ask_depth, DEPTH_WEIGHTS)

        return {
            'total_bid_qty': total_bid_qty,
            'total_ask_qty': total_ask_qty,
            'weighted_bid_qty': weighted_bid_qty,
            'weighted_ask_qty': weighted_ask_qty
        }
    except (json.JSONDecodeError, AttributeError, KeyError):
        return {
            'total_bid_qty': 0,
            'total_ask_qty': 0,
            'weighted_bid_qty': 0.0,
            'weighted_ask_qty': 0.0
        }

def calculate_bias(ratio, buyer_threshold, seller_threshold):
    """Classify market bias based on bid/ask ratio"""
    if ratio > buyer_threshold:
        return "BUYER_DOMINANT"
    elif ratio < seller_threshold:
        return "SELLER_DOMINANT"
    else:
        return "NEUTRAL"

def process_minute_candle(minute_ticks):
    """Process all ticks for a single minute to create enriched candle"""
    if len(minute_ticks) == 0:
        return None

    prices = []
    volumes = []

    for ts_ist, tick_json_str in minute_ticks:
        try:
            tick_data = json.loads(tick_json_str)
            lp = tick_data.get('lp')
            if lp is not None:
                prices.append(lp)
            vol = tick_data.get('vol')
            if vol is not None:
                volumes.append(vol)
        except (json.JSONDecodeError, AttributeError):
            continue

    if len(prices) == 0:
        return None

    # OHLCV calculation
    open_price = prices[0]
    high_price = max(prices)
    low_price = min(prices)
    close_price = prices[-1]

    if len(volumes) >= 2:
        volume = volumes[-1] - volumes[0]
        if volume < 0:
            volume = volumes[-1]
    elif len(volumes) == 1:
        volume = volumes[0]
    else:
        volume = 0

    # Depth calculation from last tick
    last_tick_json = minute_ticks[-1][1]
    depth_metrics = extract_last_tick_depth(last_tick_json)

    total_bid_qty = depth_metrics['total_bid_qty']
    total_ask_qty = depth_metrics['total_ask_qty']
    weighted_bid_qty = depth_metrics['weighted_bid_qty']
    weighted_ask_qty = depth_metrics['weighted_ask_qty']

    # Total depth ratios
    order_imbalance = total_bid_qty - total_ask_qty
    if total_ask_qty > 0:
        bid_ask_ratio = total_bid_qty / total_ask_qty
    else:
        bid_ask_ratio = 999.0 if total_bid_qty > 0 else 1.0
    bid_ask_bias = calculate_bias(bid_ask_ratio, BUYER_THRESHOLD, SELLER_THRESHOLD)

    # Weighted depth ratios
    weighted_order_imbalance = weighted_bid_qty - weighted_ask_qty
    if weighted_ask_qty > 0:
        weighted_bid_ask_ratio = weighted_bid_qty / weighted_ask_qty
    else:
        weighted_bid_ask_ratio = 999.0 if weighted_bid_qty > 0 else 1.0
    weighted_bias = calculate_bias(weighted_bid_ask_ratio, BUYER_THRESHOLD, SELLER_THRESHOLD)

    return {
        'open': open_price,
        'high': high_price,
        'low': low_price,
        'close': close_price,
        'volume': volume,
        'total_bid_qty': total_bid_qty,
        'total_ask_qty': total_ask_qty,
        'bid_ask_ratio': round(bid_ask_ratio, 4),
        'order_imbalance': order_imbalance,
        'bid_ask_bias': bid_ask_bias,
        'weighted_bid_qty': round(weighted_bid_qty, 2),
        'weighted_ask_qty': round(weighted_ask_qty, 2),
        'weighted_bid_ask_ratio': round(weighted_bid_ask_ratio, 4),
        'weighted_order_imbalance': round(weighted_order_imbalance, 2),
        'weighted_bias': weighted_bias
    }

def get_last_completed_minute():
    """Get the last fully completed minute from output database"""
    try:
        conn = sqlite3.connect(OUTPUT_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(time_minute) FROM minute_candles")
        result = cursor.fetchone()[0]
        conn.close()
        return result
    except sqlite3.OperationalError:
        return None

def process_new_ticks(last_completed_minute=None):
    """Process new ticks from tick_json_data.db"""
    try:
        source_conn = sqlite3.connect(SOURCE_DB, timeout=10)
        source_cursor = source_conn.cursor()
    except sqlite3.OperationalError as e:
        print(f"⚠️  Cannot access {SOURCE_DB}: {e} [{now_ist_str()}]")
        return 0

    query = "SELECT instrument_token, ts_ist, tick_json FROM ticks_json WHERE 1=1"

    if ALLOWED_TOKENS is not None:
        allowed_str = ','.join(str(t) for t in ALLOWED_TOKENS)
        query += f" AND instrument_token IN ({allowed_str})"

    if last_completed_minute:
        query += f" AND strftime('%Y-%m-%d %H:%M', ts_ist) > '{last_completed_minute}'"

    query += " ORDER BY ts_ist ASC"

    source_cursor.execute(query)

    minute_buckets = defaultdict(lambda: defaultdict(list))
    total_ticks = 0

    for row in source_cursor:
        instrument_token, ts_ist, tick_json = row
        if ALLOWED_TOKENS is not None and instrument_token not in ALLOWED_TOKENS:
            continue
        time_minute = parse_ist_minute(ts_ist)
        minute_buckets[instrument_token][time_minute].append((ts_ist, tick_json))
        total_ticks += 1

    source_conn.close()

    if total_ticks == 0:
        return 0

    output_conn = sqlite3.connect(OUTPUT_DB)
    output_cursor = output_conn.cursor()

    processed_count = 0

    for instrument_token, minutes in minute_buckets.items():
        for time_minute, ticks in minutes.items():
            ticks_sorted = sorted(ticks, key=lambda x: x[0])
            candle_data = process_minute_candle(ticks_sorted)

            if candle_data is None:
                continue

            # Get symbol from token mapping
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
            symbol = TOKENS.get(instrument_token, f"UNKNOWN_{instrument_token}")
            
            output_cursor.execute("""
                INSERT OR REPLACE INTO minute_candles
                (instrument_token, symbol, time_minute, open, high, low, close, volume,
                 total_bid_qty, total_ask_qty, bid_ask_ratio, order_imbalance, bid_ask_bias,
                 weighted_bid_qty, weighted_ask_qty, weighted_bid_ask_ratio,
                 weighted_order_imbalance, weighted_bias)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                instrument_token, symbol, time_minute,
                candle_data['open'], candle_data['high'], candle_data['low'],
                candle_data['close'], candle_data['volume'],
                candle_data['total_bid_qty'], candle_data['total_ask_qty'],
                candle_data['bid_ask_ratio'], candle_data['order_imbalance'],
                candle_data['bid_ask_bias'], candle_data['weighted_bid_qty'],
                candle_data['weighted_ask_qty'], candle_data['weighted_bid_ask_ratio'],
                candle_data['weighted_order_imbalance'], candle_data['weighted_bias']
            ))
            processed_count += 1

    output_conn.commit()
    output_conn.close()

    return processed_count

# ============================================================================
# DAEMON MAIN LOOP
# ============================================================================

def main():
    """Main daemon loop"""
    print("=" * 80)
    print("🕯️  1-Minute Candle Builder - DAEMON MODE")
    print("=" * 80)
    print(f"📊 Processing interval: {PROCESSING_INTERVAL} seconds")
    print(f"📁 Source: {SOURCE_DB}")
    print(f"📁 Output: {OUTPUT_DB}")

    if ALLOWED_TOKENS:
        print(f"🎯 Instruments: {sorted(ALLOWED_TOKENS)}")
    else:
        print(f"🎯 Instruments: ALL")

    print(f"🕐 Started at: {now_ist_str('%Y-%m-%d %H:%M:%S')} IST")
    print("=" * 80)

    # Initialize database
    init_output_db()
    print(f"✅ Database initialized [{now_ist_str()}]")

    cycle_count = 0

    while not shutdown_requested:
        cycle_count += 1
        cycle_start = time.time()

        try:
            # Get last processed minute
            last_minute = get_last_completed_minute()

            # Process new data
            processed = process_new_ticks(last_completed_minute=last_minute)

            cycle_duration = time.time() - cycle_start

            if processed > 0:
                print(f"[{now_ist_str()}] "
                      f"Cycle #{cycle_count}: Processed {processed} candles "
                      f"({cycle_duration:.2f}s)")

        except Exception as e:
            print(f"❌ Error in cycle #{cycle_count}: {e} [{now_ist_str()}]")

        # Sleep until next cycle
        time.sleep(PROCESSING_INTERVAL)

    print(f"\n✅ Candle Builder stopped gracefully [{now_ist_str('%Y-%m-%d %H:%M:%S')}]")
    sys.exit(0)

if __name__ == "__main__":
    main()
