#!/usr/bin/env python3
"""
OI CATEGORY BUILDER - CONTINUOUS MODE (FIXED)
Classifies OI behavior for Futures (BANKNIFTY_FUT, NIFTY_FUT)
Categories: LB (Long Build-up), SB (Short Build-up), 
            SC (Short Covering), LU (Long Unwinding)
"""

import sqlite3
import time
from datetime import datetime

# =====================================================
# CONFIG
# =====================================================

CANDLE_DB = "minute_candles.db"
OI_DB = "oi_analysis.db"

# ---- FUTURE INSTRUMENT TOKENS (LOCKED) ----
FUTURE_TOKENS = {
    13568258: "BANKNIFTY_FUT",
    256265: "NIFTY_FUT"
}

# =====================================================
# HELPER
# =====================================================

def get_oi_category(price_change, oi_change):
    """
    Classify OI behavior based on price and OI change
    
    LB (Long Build-up):    Price ↑ + OI ↑ → Bullish
    SB (Short Build-up):   Price ↓ + OI ↑ → Bearish
    SC (Short Covering):   Price ↑ + OI ↓ → Bullish
    LU (Long Unwinding):   Price ↓ + OI ↓ → Bearish
    NA: No significant change
    """
    # Add threshold to avoid noise
    price_threshold = 0.1  # 0.1 point threshold
    oi_threshold = 10      # 10 contracts threshold
    
    if abs(price_change) < price_threshold and abs(oi_change) < oi_threshold:
        return "NA"
    
    if price_change > 0 and oi_change > oi_threshold:
        return "LB"
    elif price_change < 0 and oi_change > oi_threshold:
        return "SB"
    elif price_change > 0 and oi_change < -oi_threshold:
        return "SC"
    elif price_change < 0 and oi_change < -oi_threshold:
        return "LU"
    else:
        return "NA"

# =====================================================
# DATABASE INITIALIZATION
# =====================================================

def init_databases():
    """Initialize database connections and tables"""
    try:
        # Input DB
        candle_conn = sqlite3.connect(CANDLE_DB)
        candle_conn.row_factory = sqlite3.Row
        
        # Output DB
        oi_conn = sqlite3.connect(OI_DB)
        oi_cur = oi_conn.cursor()
        
        oi_cur.execute("""
        CREATE TABLE IF NOT EXISTS oi_category_1m (
            time_minute TEXT,
            instrument_token INTEGER,
            symbol TEXT,
            open REAL,
            close REAL,
            price_change REAL,
            oi_change INTEGER,
            oi_category TEXT,
            PRIMARY KEY (time_minute, instrument_token)
        )
        """)
        
        oi_cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_oi_time 
        ON oi_category_1m(time_minute)
        """)
        
        oi_cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_oi_token 
        ON oi_category_1m(instrument_token)
        """)
        
        oi_conn.commit()
        
        return candle_conn, oi_conn
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise

# =====================================================
# MAIN PROCESS (CONTINUOUS MODE)
# =====================================================

def process_new_candles(candle_conn, oi_conn):
    """Process only new candles that haven't been categorized yet"""
    try:
        candle_cur = candle_conn.cursor()
        oi_cur = oi_conn.cursor()
        
        # Get the last processed time
        oi_cur.execute("""
            SELECT COALESCE(MAX(time_minute), '2000-01-01 00:00:00') as last_time
            FROM oi_category_1m
        """)
        last_time = oi_cur.fetchone()[0]
        
        # Get only NEW candles for future tokens
        placeholders = ",".join("?" * len(FUTURE_TOKENS))
        
        query = f"""
            SELECT 
                c.time_minute,
                c.instrument_token,
                c.symbol,
                c.open,
                c.close,
                COALESCE(c.oi_change, 0) as oi_change
            FROM candles_1m c
            WHERE c.instrument_token IN ({placeholders})
            AND c.time_minute > ?
            ORDER BY c.time_minute ASC
        """
        
        params = tuple(FUTURE_TOKENS.keys()) + (last_time,)
        candle_cur.execute(query, params)
        
        rows = candle_cur.fetchall()
        
        if not rows:
            return 0  # No new candles
        
        insert_rows = []
        
        for r in rows:
            token = r["instrument_token"]
            symbol = r["symbol"]
            time_minute = r["time_minute"]
            open_p = r["open"]
            close_p = r["close"]
            oi_chg = r["oi_change"]
            
            # Calculate price change
            price_chg = close_p - open_p
            
            # Get OI category
            category = get_oi_category(price_chg, oi_chg)
            
            insert_rows.append((
                time_minute,
                token,
                symbol,
                open_p,
                close_p,
                price_chg,
                oi_chg,
                category
            ))
        
        # Insert all new rows
        if insert_rows:
            oi_cur.executemany("""
                INSERT OR REPLACE INTO oi_category_1m
                (time_minute, instrument_token, symbol,
                 open, close, price_change, oi_change, oi_category)
                VALUES (?,?,?,?,?,?,?,?)
            """, insert_rows)
            
            oi_conn.commit()
        
        return len(insert_rows)
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return 0
    except Exception as e:
        print(f"❌ Error processing candles: {e}")
        import traceback
        traceback.print_exc()
        return 0

# =====================================================
# MAIN LOOP
# =====================================================

def main():
    print("🚀 OI CATEGORY BUILDER - CONTINUOUS MODE (FIXED)")
    print(f"📊 Tracking: {len(FUTURE_TOKENS)} futures")
    print(f"📦 Input:  {CANDLE_DB}")
    print(f"📦 Output: {OI_DB}")
    print("🔄 Running continuously (Ctrl+C to stop)...\n")
    
    # Initialize databases
    try:
        candle_conn, oi_conn = init_databases()
        print("✅ Databases initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize databases: {e}")
        return
    
    consecutive_empty = 0
    error_count = 0
    max_errors = 10
    
    while True:
        try:
            # Process new candles
            processed = process_new_candles(candle_conn, oi_conn)
            
            if processed > 0:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] ✅ Processed {processed} new candle(s)")
                consecutive_empty = 0
                error_count = 0  # Reset error count on success
            else:
                consecutive_empty += 1
                # Print waiting message every 10 cycles (10 minutes)
                if consecutive_empty % 10 == 0:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] ⏳ Waiting for new candles... ({consecutive_empty} checks)")
            
            # Wait 60 seconds before next check
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down gracefully...")
            break
            
        except Exception as e:
            error_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] ❌ Error in main loop: {e}")
            
            if error_count >= max_errors:
                print(f"❌ Too many consecutive errors ({max_errors}). Exiting...")
                break
            
            print(f"⏸️  Pausing for 5 seconds before retry... (Error {error_count}/{max_errors})")
            time.sleep(5)
    
    # Cleanup
    try:
        candle_conn.close()
        oi_conn.close()
        print("✅ Database connections closed")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"⚠️  Error during cleanup: {e}")

if __name__ == "__main__":
    main()
