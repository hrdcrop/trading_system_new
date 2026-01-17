#!/usr/bin/env python3
"""
OI Category Builder v2 - PRODUCTION HARDENED
Reads ONLY from tick_json_data.db (parallel to candle_builder_1m.py)
Computes OI categories for BANKNIFTY and NIFTY futures only
"""

import sqlite3
import json
from datetime import datetime
from collections import defaultdict

# Database paths
SOURCE_DB = "tick_json_data.db"
OUTPUT_DB = "oi_analysis.db"

# STRICT: Only these instrument tokens are allowed
ALLOWED_FUTURES = {
    12601346,  # BANKNIFTY
    12602626   # NIFTY
}


def init_output_db():
    """Initialize output database with schema"""
    conn = sqlite3.connect(OUTPUT_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS futures_oi_category_1m (
            instrument_token INTEGER NOT NULL,
            time_minute TEXT NOT NULL,
            price_start REAL NOT NULL,
            price_end REAL NOT NULL,
            oi_start INTEGER NOT NULL,
            oi_end INTEGER NOT NULL,
            price_change REAL NOT NULL,
            oi_change INTEGER NOT NULL,
            oi_category TEXT NOT NULL,
            PRIMARY KEY (instrument_token, time_minute)
        )
    """)
    
    # Index for faster time-based queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_time_minute 
        ON futures_oi_category_1m(time_minute)
    """)
    
    conn.commit()
    conn.close()
    print(f"✓ Initialized {OUTPUT_DB}")


def get_oi_category(price_change, oi_change):
    """
    Determine OI category based on price and OI changes
    
    SKIP if either change is zero (no clear directional signal)
    
    Returns:
        str or None: Category code or None if conditions not met
    """
    # MANDATORY: Skip if no change in price or OI
    if price_change == 0 or oi_change == 0:
        return None
    
    if price_change > 0 and oi_change > 0:
        return "LB"  # Long Build-up
    elif price_change < 0 and oi_change > 0:
        return "SB"  # Short Build-up
    elif price_change > 0 and oi_change < 0:
        return "SC"  # Short Covering
    elif price_change < 0 and oi_change < 0:
        return "LU"  # Long Unwinding
    else:
        return None


def parse_ist_minute(ts_ist_str):
    """
    Extract IST minute bucket from timestamp string
    ts_ist is ALREADY in IST - no timezone conversion needed
    
    Args:
        ts_ist_str: Timestamp string in IST (e.g., "2026-01-17 09:21:34")
    
    Returns:
        str: Minute bucket in format "YYYY-MM-DD HH:MM"
    """
    # Parse and truncate to minute (no timezone conversion - already IST)
    dt = datetime.strptime(ts_ist_str, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d %H:%M")


def process_minute_data(minute_ticks):
    """
    Process ticks for a single minute bucket
    
    Args:
        minute_ticks: List of (ts_ist, tick_json_str) tuples, sorted by timestamp
    
    Returns:
        dict or None: Calculated metrics or None if insufficient/invalid data
    """
    # MANDATORY: Need at least 2 ticks (first and last)
    if len(minute_ticks) < 2:
        return None
    
    # Parse first and last tick JSON
    try:
        first_tick_json = json.loads(minute_ticks[0][1])
        last_tick_json = json.loads(minute_ticks[-1][1])
    except (json.JSONDecodeError, IndexError):
        return None  # Skip if JSON parsing fails
    
    # MANDATORY: Extract OI values (must exist and be valid)
    oi_start = first_tick_json.get('oi')
    oi_end = last_tick_json.get('oi')
    
    if oi_start is None or oi_end is None:
        return None  # Skip if OI not present
    
    # MANDATORY: Extract price values (must exist and be valid)
    price_start = first_tick_json.get('lp')
    price_end = last_tick_json.get('lp')
    
    if price_start is None or price_end is None:
        return None  # Skip if price not present
    
    # Calculate changes
    price_change = price_end - price_start
    oi_change = oi_end - oi_start
    
    # Determine category (returns None if price_change==0 or oi_change==0)
    category = get_oi_category(price_change, oi_change)
    
    if category is None:
        return None  # Skip neutral/no-change cases
    
    return {
        'price_start': price_start,
        'price_end': price_end,
        'oi_start': oi_start,
        'oi_end': oi_end,
        'price_change': price_change,
        'oi_change': oi_change,
        'oi_category': category
    }


def get_last_processed_minute():
    """
    Get the last fully processed IST minute from output database
    This enables incremental processing - only fetch newer ticks
    
    Returns:
        str or None: Last processed time_minute (IST) or None if no data
    """
    try:
        conn = sqlite3.connect(OUTPUT_DB)
        cursor = conn.cursor()
        
        # Get the maximum time_minute already processed
        cursor.execute("""
            SELECT MAX(time_minute)
            FROM futures_oi_category_1m
        """)
        
        result = cursor.fetchone()[0]
        conn.close()
        
        return result
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return None


def process_new_ticks(last_processed_minute=None):
    """
    Process new ticks from tick_json_data.db
    INCREMENTAL: Only process ticks newer than last_processed_minute
    
    Args:
        last_processed_minute: Last processed IST minute (format: "YYYY-MM-DD HH:MM")
    """
    # Connect to source database
    source_conn = sqlite3.connect(SOURCE_DB)
    source_cursor = source_conn.cursor()
    
    # STRICT FILTERING at SQL level:
    # 1. Only ALLOWED_FUTURES instrument tokens
    # 2. Only ticks with OI present
    # 3. Only ticks newer than last processed minute (INCREMENTAL)
    
    allowed_tokens_str = ','.join(str(t) for t in ALLOWED_FUTURES)
    
    query = f"""
        SELECT instrument_token, ts_ist, tick_json
        FROM ticks_json
        WHERE instrument_token IN ({allowed_tokens_str})
          AND json_extract(tick_json, '$.oi') IS NOT NULL
    """
    
    # INCREMENTAL PROCESSING: Only fetch ticks after last processed minute
    if last_processed_minute:
        # Add 1 minute to avoid reprocessing the last minute
        # Compare at minute level: ts_ist > "YYYY-MM-DD HH:MM:59"
        query += f" AND ts_ist > '{last_processed_minute}:59'"
        print(f"📊 Incremental mode: Fetching ticks after {last_processed_minute}")
    else:
        print(f"📊 Full scan mode: Processing all available data")
    
    query += " ORDER BY ts_ist ASC"
    
    source_cursor.execute(query)
    
    # Group ticks by instrument and IST minute bucket
    # Structure: {instrument_token: {time_minute: [(ts_ist, tick_json), ...]}}
    minute_buckets = defaultdict(lambda: defaultdict(list))
    
    total_ticks = 0
    for row in source_cursor:
        instrument_token, ts_ist, tick_json = row
        
        # DOUBLE VALIDATION: Ensure instrument is allowed (defense in depth)
        if instrument_token not in ALLOWED_FUTURES:
            continue
        
        # Extract IST minute bucket (no timezone conversion - already IST)
        time_minute = parse_ist_minute(ts_ist)
        
        # Add to bucket
        minute_buckets[instrument_token][time_minute].append((ts_ist, tick_json))
        total_ticks += 1
    
    source_conn.close()
    print(f"✓ Fetched {total_ticks} ticks for {len(minute_buckets)} instruments")
    
    # Process each instrument-minute bucket
    output_conn = sqlite3.connect(OUTPUT_DB)
    output_cursor = output_conn.cursor()
    
    processed_count = 0
    skipped_count = 0
    
    for instrument_token, minutes in minute_buckets.items():
        for time_minute, ticks in minutes.items():
            # Sort ticks by timestamp to ensure correct first/last order
            ticks_sorted = sorted(ticks, key=lambda x: x[0])
            
            # Process minute data (returns None if invalid/insufficient)
            result = process_minute_data(ticks_sorted)
            
            if result is None:
                skipped_count += 1
                continue
            
            # INSERT OR REPLACE for idempotent execution
            # Safe to re-run - will update existing rows
            output_cursor.execute("""
                INSERT OR REPLACE INTO futures_oi_category_1m
                (instrument_token, time_minute, price_start, price_end,
                 oi_start, oi_end, price_change, oi_change, oi_category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                instrument_token,
                time_minute,
                result['price_start'],
                result['price_end'],
                result['oi_start'],
                result['oi_end'],
                result['price_change'],
                result['oi_change'],
                result['oi_category']
            ))
            
            processed_count += 1
    
    output_conn.commit()
    output_conn.close()
    
    print(f"✓ Processed: {processed_count} minute-buckets")
    print(f"✓ Skipped: {skipped_count} minute-buckets (insufficient data or neutral)")


def main():
    """Main execution flow"""
    print("=" * 60)
    print("OI Category Builder v2 - PRODUCTION")
    print("=" * 60)
    print(f"Allowed instruments: {sorted(ALLOWED_FUTURES)}")
    print("=" * 60)
    
    # Initialize output database
    init_output_db()
    
    # INCREMENTAL: Get last processed minute for efficient resumption
    last_minute = get_last_processed_minute()
    
    # Process only new ticks (incremental)
    process_new_ticks(last_processed_minute=last_minute)
    
    print("=" * 60)
    print("✓ OI Category Builder completed successfully")
    print("=" * 60)


if __name__ == "__main__":
    main()
