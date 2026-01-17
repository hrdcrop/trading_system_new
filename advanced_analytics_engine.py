#!/usr/bin/env python3
"""
ADVANCED ANALYTICS ENGINE WITH PATTERN RECOGNITION
Features:
- Historical pattern matching
- Support/Resistance auto-detection
- Pivot points calculation
- Volume Profile analysis
- Fibonacci levels
- Trend strength indicators
"""

import sqlite3
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from collections import deque
import json

# =====================================================
# CONFIG
# =====================================================

CANDLE_DB = "minute_candles.db"
ANALYTICS_DB = "market_analytics.db"
ADVANCED_DB = "advanced_analytics.db"

# =====================================================
# DATABASE SETUP
# =====================================================

def init_advanced_db():
    """Initialize advanced analytics database"""
    conn = sqlite3.connect(ADVANCED_DB)
    cur = conn.cursor()
    
    # Support/Resistance table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS support_resistance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        
        support_levels TEXT,
        resistance_levels TEXT,
        strength_scores TEXT,
        
        last_updated TEXT
    )
    """)
    
    # Pivot points table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pivot_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        
        pivot REAL,
        r1 REAL, r2 REAL, r3 REAL,
        s1 REAL, s2 REAL, s3 REAL,
        
        pivot_type TEXT
    )
    """)
    
    # Volume profile table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS volume_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL,
        
        poc REAL,
        vah REAL,
        val REAL,
        
        profile_data TEXT
    )
    """)
    
    # Fibonacci levels table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fibonacci_levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL,
        
        swing_high REAL,
        swing_low REAL,
        
        fib_0 REAL,
        fib_236 REAL,
        fib_382 REAL,
        fib_50 REAL,
        fib_618 REAL,
        fib_786 REAL,
        fib_100 REAL,
        
        trend_direction TEXT
    )
    """)
    
    # Pattern recognition table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pattern_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL,
        
        pattern_name TEXT,
        pattern_type TEXT,
        confidence REAL,
        expected_move REAL,
        
        entry_price REAL,
        target_price REAL,
        stop_loss REAL
    )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sr_symbol ON support_resistance(symbol)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pivot_symbol ON pivot_points(symbol)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vp_symbol ON volume_profile(symbol)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fib_symbol ON fibonacci_levels(symbol)")
    
    conn.commit()
    return conn

# =====================================================
# SUPPORT/RESISTANCE DETECTION
# =====================================================

def detect_support_resistance(candles: List[Dict], lookback: int = 50) -> Tuple[List[float], List[float]]:
    """
    Detect support and resistance levels using swing highs/lows
    """
    if len(candles) < lookback:
        return [], []
    
    highs = [c['high'] for c in candles[-lookback:]]
    lows = [c['low'] for c in candles[-lookback:]]
    
    # Find swing highs (resistance)
    resistance_levels = []
    for i in range(2, len(highs) - 2):
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
            highs[i] > highs[i+1] and highs[i] > highs[i+2]):
            resistance_levels.append(highs[i])
    
    # Find swing lows (support)
    support_levels = []
    for i in range(2, len(lows) - 2):
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
            lows[i] < lows[i+1] and lows[i] < lows[i+2]):
            support_levels.append(lows[i])
    
    # Cluster nearby levels
    support_levels = cluster_levels(support_levels)
    resistance_levels = cluster_levels(resistance_levels)
    
    return support_levels[:5], resistance_levels[:5]

def cluster_levels(levels: List[float], threshold_pct: float = 0.5) -> List[float]:
    """Group nearby levels together"""
    if not levels:
        return []
    
    levels = sorted(levels)
    clustered = []
    current_cluster = [levels[0]]
    
    for i in range(1, len(levels)):
        if abs(levels[i] - current_cluster[-1]) / current_cluster[-1] * 100 < threshold_pct:
            current_cluster.append(levels[i])
        else:
            clustered.append(sum(current_cluster) / len(current_cluster))
            current_cluster = [levels[i]]
    
    if current_cluster:
        clustered.append(sum(current_cluster) / len(current_cluster))
    
    return clustered

# =====================================================
# PIVOT POINTS CALCULATION
# =====================================================

def calculate_pivot_points(high: float, low: float, close: float, 
                          pivot_type: str = "standard") -> Dict[str, float]:
    """
    Calculate pivot points
    Types: standard, fibonacci, woodie, camarilla
    """
    if pivot_type == "standard":
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
    elif pivot_type == "fibonacci":
        pivot = (high + low + close) / 3
        r1 = pivot + 0.382 * (high - low)
        r2 = pivot + 0.618 * (high - low)
        r3 = pivot + (high - low)
        s1 = pivot - 0.382 * (high - low)
        s2 = pivot - 0.618 * (high - low)
        s3 = pivot - (high - low)
        
    elif pivot_type == "woodie":
        pivot = (high + low + 2 * close) / 4
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
    elif pivot_type == "camarilla":
        pivot = (high + low + close) / 3
        r1 = close + 1.1 * (high - low) / 12
        r2 = close + 1.1 * (high - low) / 6
        r3 = close + 1.1 * (high - low) / 4
        s1 = close - 1.1 * (high - low) / 12
        s2 = close - 1.1 * (high - low) / 6
        s3 = close - 1.1 * (high - low) / 4
    
    else:  # default to standard
        return calculate_pivot_points(high, low, close, "standard")
    
    return {
        "pivot": pivot,
        "r1": r1, "r2": r2, "r3": r3,
        "s1": s1, "s2": s2, "s3": s3
    }

# =====================================================
# VOLUME PROFILE ANALYSIS
# =====================================================

def calculate_volume_profile(candles: List[Dict], num_bins: int = 20) -> Dict:
    """
    Calculate Volume Profile - POC, VAH, VAL
    POC = Point of Control (highest volume price)
    VAH = Value Area High
    VAL = Value Area Low
    """
    if len(candles) < 10:
        return {}
    
    # Get price range
    prices = [c['close'] for c in candles]
    volumes = [c['volume'] for c in candles]
    
    min_price = min(prices)
    max_price = max(prices)
    
    # Create price bins
    bin_size = (max_price - min_price) / num_bins
    bins = {}
    
    for i, price in enumerate(prices):
        bin_idx = int((price - min_price) / bin_size)
        if bin_idx >= num_bins:
            bin_idx = num_bins - 1
        
        bin_price = min_price + (bin_idx + 0.5) * bin_size
        
        if bin_price not in bins:
            bins[bin_price] = 0
        bins[bin_price] += volumes[i]
    
    # Find POC (Point of Control)
    poc = max(bins.keys(), key=lambda k: bins[k])
    
    # Calculate Value Area (70% of volume)
    total_volume = sum(bins.values())
    target_volume = total_volume * 0.70
    
    sorted_bins = sorted(bins.items(), key=lambda x: x[1], reverse=True)
    
    va_volume = 0
    va_prices = []
    
    for price, vol in sorted_bins:
        va_volume += vol
        va_prices.append(price)
        if va_volume >= target_volume:
            break
    
    vah = max(va_prices) if va_prices else poc
    val = min(va_prices) if va_prices else poc
    
    return {
        "poc": poc,
        "vah": vah,
        "val": val,
        "profile": bins
    }

# =====================================================
# FIBONACCI LEVELS
# =====================================================

def calculate_fibonacci_levels(swing_high: float, swing_low: float, 
                               trend: str = "uptrend") -> Dict[str, float]:
    """
    Calculate Fibonacci retracement levels
    """
    diff = swing_high - swing_low
    
    if trend == "uptrend":
        # Retracement from high to low
        return {
            "0": swing_high,
            "23.6": swing_high - 0.236 * diff,
            "38.2": swing_high - 0.382 * diff,
            "50": swing_high - 0.5 * diff,
            "61.8": swing_high - 0.618 * diff,
            "78.6": swing_high - 0.786 * diff,
            "100": swing_low
        }
    else:
        # Retracement from low to high
        return {
            "0": swing_low,
            "23.6": swing_low + 0.236 * diff,
            "38.2": swing_low + 0.382 * diff,
            "50": swing_low + 0.5 * diff,
            "61.8": swing_low + 0.618 * diff,
            "78.6": swing_low + 0.786 * diff,
            "100": swing_high
        }

def find_swing_points(candles: List[Dict], lookback: int = 20) -> Tuple[float, float]:
    """Find recent swing high and swing low"""
    if len(candles) < lookback:
        return 0, 0
    
    recent = candles[-lookback:]
    swing_high = max(c['high'] for c in recent)
    swing_low = min(c['low'] for c in recent)
    
    return swing_high, swing_low

# =====================================================
# PATTERN RECOGNITION (Advanced)
# =====================================================

def detect_advanced_patterns(candles: List[Dict]) -> List[Dict]:
    """
    Detect advanced chart patterns:
    - Head and Shoulders
    - Double Top/Bottom
    - Triangle patterns
    - Cup and Handle
    """
    patterns = []
    
    if len(candles) < 20:
        return patterns
    
    # Double Top detection
    dt = detect_double_top(candles)
    if dt:
        patterns.append(dt)
    
    # Double Bottom detection
    db = detect_double_bottom(candles)
    if db:
        patterns.append(db)
    
    # Head and Shoulders
    hs = detect_head_shoulders(candles)
    if hs:
        patterns.append(hs)
    
    return patterns

def detect_double_top(candles: List[Dict], tolerance: float = 0.02) -> Optional[Dict]:
    """Detect Double Top pattern"""
    if len(candles) < 15:
        return None
    
    recent = candles[-15:]
    highs = [c['high'] for c in recent]
    
    # Find two peaks
    peaks = []
    for i in range(1, len(highs) - 1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            peaks.append((i, highs[i]))
    
    if len(peaks) >= 2:
        # Check if last two peaks are similar
        peak1 = peaks[-2][1]
        peak2 = peaks[-1][1]
        
        if abs(peak1 - peak2) / peak1 < tolerance:
            return {
                "pattern": "DOUBLE_TOP",
                "type": "BEARISH",
                "confidence": 0.75,
                "entry": recent[-1]['close'],
                "target": min(c['low'] for c in recent[peaks[-2][0]:peaks[-1][0]]),
                "stop_loss": max(peak1, peak2) * 1.01
            }
    
    return None

def detect_double_bottom(candles: List[Dict], tolerance: float = 0.02) -> Optional[Dict]:
    """Detect Double Bottom pattern"""
    if len(candles) < 15:
        return None
    
    recent = candles[-15:]
    lows = [c['low'] for c in recent]
    
    # Find two troughs
    troughs = []
    for i in range(1, len(lows) - 1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            troughs.append((i, lows[i]))
    
    if len(troughs) >= 2:
        # Check if last two troughs are similar
        trough1 = troughs[-2][1]
        trough2 = troughs[-1][1]
        
        if abs(trough1 - trough2) / trough1 < tolerance:
            return {
                "pattern": "DOUBLE_BOTTOM",
                "type": "BULLISH",
                "confidence": 0.75,
                "entry": recent[-1]['close'],
                "target": max(c['high'] for c in recent[troughs[-2][0]:troughs[-1][0]]),
                "stop_loss": min(trough1, trough2) * 0.99
            }
    
    return None

def detect_head_shoulders(candles: List[Dict]) -> Optional[Dict]:
    """Detect Head and Shoulders pattern"""
    if len(candles) < 20:
        return None
    
    recent = candles[-20:]
    highs = [c['high'] for c in recent]
    
    # Find three peaks
    peaks = []
    for i in range(2, len(highs) - 2):
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and
            highs[i] > highs[i+1] and highs[i] > highs[i+2]):
            peaks.append((i, highs[i]))
    
    if len(peaks) >= 3:
        # Check H&S structure: left shoulder < head > right shoulder
        left = peaks[-3][1]
        head = peaks[-2][1]
        right = peaks[-1][1]
        
        if head > left and head > right and abs(left - right) / left < 0.05:
            # Find neckline
            neckline = min(c['low'] for c in recent[peaks[-3][0]:peaks[-1][0]])
            
            return {
                "pattern": "HEAD_AND_SHOULDERS",
                "type": "BEARISH",
                "confidence": 0.8,
                "entry": neckline,
                "target": neckline - (head - neckline),
                "stop_loss": head * 1.01
            }
    
    return None

# =====================================================
# MAIN PROCESSING
# =====================================================

def process_advanced_analytics(symbol: str, conn) -> None:
    """Process all advanced analytics for a symbol"""
    try:
        # Get recent candles
        candle_conn = sqlite3.connect(CANDLE_DB)
        candle_conn.row_factory = sqlite3.Row
        cur = candle_conn.cursor()
        
        cur.execute("""
            SELECT * FROM candles_1m
            WHERE symbol = ?
            ORDER BY time_minute DESC
            LIMIT 200
        """, (symbol,))
        
        rows = cur.fetchall()
        candle_conn.close()
        
        if not rows:
            return
        
        candles = [dict(row) for row in reversed(rows)]
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:00")
        
        # 1. Support/Resistance
        support, resistance = detect_support_resistance(candles)
        if support or resistance:
            save_support_resistance(conn, symbol, support, resistance, timestamp)
        
        # 2. Pivot Points (daily)
        if len(candles) > 0:
            last_candle = candles[-1]
            pivots = calculate_pivot_points(
                last_candle['high'],
                last_candle['low'],
                last_candle['close']
            )
            save_pivot_points(conn, symbol, pivots, timestamp)
        
        # 3. Volume Profile
        vp = calculate_volume_profile(candles)
        if vp:
            save_volume_profile(conn, symbol, vp, timestamp)
        
        # 4. Fibonacci Levels
        swing_high, swing_low = find_swing_points(candles)
        if swing_high > 0 and swing_low > 0:
            fib_levels = calculate_fibonacci_levels(swing_high, swing_low, "uptrend")
            save_fibonacci_levels(conn, symbol, swing_high, swing_low, fib_levels, timestamp)
        
        # 5. Pattern Recognition
        patterns = detect_advanced_patterns(candles)
        for pattern in patterns:
            save_pattern_signal(conn, symbol, pattern, timestamp)
        
        print(f"✅ {symbol} - Advanced analytics updated")
        
    except Exception as e:
        print(f"[ADVANCED ERR] {symbol}: {e}")
        import traceback
        traceback.print_exc()

# =====================================================
# SAVE FUNCTIONS
# =====================================================

def save_support_resistance(conn, symbol: str, support: List[float], 
                           resistance: List[float], timestamp: str):
    """Save support/resistance levels"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO support_resistance
        (timestamp, symbol, timeframe, support_levels, resistance_levels, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, symbol, "1m", json.dumps(support), json.dumps(resistance), timestamp))
    conn.commit()

def save_pivot_points(conn, symbol: str, pivots: Dict, timestamp: str):
    """Save pivot points"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pivot_points
        (date, symbol, pivot, r1, r2, r3, s1, s2, s3, pivot_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp[:10], symbol, pivots['pivot'],
          pivots['r1'], pivots['r2'], pivots['r3'],
          pivots['s1'], pivots['s2'], pivots['s3'], "standard"))
    conn.commit()

def save_volume_profile(conn, symbol: str, vp: Dict, timestamp: str):
    """Save volume profile"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO volume_profile
        (timestamp, symbol, poc, vah, val, profile_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, symbol, vp['poc'], vp['vah'], vp['val'], 
          json.dumps(vp.get('profile', {}))))
    conn.commit()

def save_fibonacci_levels(conn, symbol: str, swing_high: float, swing_low: float,
                         fib: Dict, timestamp: str):
    """Save fibonacci levels"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fibonacci_levels
        (timestamp, symbol, swing_high, swing_low,
         fib_0, fib_236, fib_382, fib_50, fib_618, fib_786, fib_100,
         trend_direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, symbol, swing_high, swing_low,
          fib['0'], fib['23.6'], fib['38.2'], fib['50'], 
          fib['61.8'], fib['78.6'], fib['100'], "uptrend"))
    conn.commit()

def save_pattern_signal(conn, symbol: str, pattern: Dict, timestamp: str):
    """Save pattern signal"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pattern_signals
        (timestamp, symbol, pattern_name, pattern_type, confidence,
         entry_price, target_price, stop_loss)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, symbol, pattern['pattern'], pattern['type'],
          pattern['confidence'], pattern.get('entry', 0),
          pattern.get('target', 0), pattern.get('stop_loss', 0)))
    conn.commit()

# =====================================================
# MAIN LOOP
# =====================================================

def main():
    print("🚀 Advanced Analytics Engine Started")
    
    conn = init_advanced_db()
    print("✅ Database initialized\n")
    
    symbols = ["NIFTY", "BANKNIFTY", "HDFCBANK", "ICICIBANK", "RELIANCE"]
    
    while True:
        try:
            for symbol in symbols:
                process_advanced_analytics(symbol, conn)
            
            time.sleep(300)  # Every 5 minutes
            
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(10)
    
    conn.close()

if __name__ == "__main__":
    import time
    main()
