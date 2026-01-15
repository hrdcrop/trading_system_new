#!/usr/bin/env python3
"""
PROFESSIONAL ALERT ENGINE v1.0
Context-Aware Market Decision System

Philosophy:
- OI = INTENT (anchor)
- Depth = EXECUTION (trigger)
- Index/Stocks = CONFIRMATION (filter)
- Regime/VIX = CONTEXT (action mapper)

NOT a signal generator. A market state analyzer.
"""

import sqlite3
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import statistics

# =====================================================
# CONFIG
# =====================================================

CANDLE_DB = "minute_candles.db"
OI_DB = "oi_analysis.db"
ANALYTICS_DB = "market_analytics.db"
ALERT_DB = "alerts_pro.db"

# Tokens
FUTURE_TOKENS = {13568258: "BANKNIFTY_FUT", 256265: "NIFTY_FUT"}
INDEX_TOKENS = {12601346: "BANKNIFTY", 12602626: "NIFTY"}
BANKING_STOCKS = [341249, 1270529, 779521, 492033, 1510401, 1346049]  # HDFC, ICICI, SBI, KOTAK, AXIS, INDUSIND
NBFC_STOCKS = [12622082, 12621826, 12804354, 12706818, 12628994]
VIX_TOKEN = 264969

# Thresholds
MIN_CONFIDENCE = 55
BID_ASK_BUY_THRESHOLD = 1.5
BID_ASK_SELL_THRESHOLD = 0.67
ORDER_IMBALANCE_THRESHOLD = 100
HIGH_VIX = 18
LOW_VIX = 12

# =====================================================
# ENUMS
# =====================================================

class MarketRegime(Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"

class VixState(Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

class DepthBias(Enum):
    BUYER_DOMINANT = "BUYER_DOMINANT"
    SELLER_DOMINANT = "SELLER_DOMINANT"
    NEUTRAL = "NEUTRAL"

class Action(Enum):
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"
    SELL_CE_PREMIUM = "SELL_CE_PREMIUM"
    SELL_PE_PREMIUM = "SELL_PE_PREMIUM"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"

# =====================================================
# DATA STRUCTURES
# =====================================================

@dataclass
class MarketContext:
    time: str
    symbol: str
    future_oi: str
    depth_bias: str
    index_bias: str
    sector_bias: str
    market_bias: str
    regime: str
    vix_state: str
    confidence: int
    action: str

# =====================================================
# DATABASE SETUP
# =====================================================

def init_alert_db():
    conn = sqlite3.connect(ALERT_DB)
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts_final (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT NOT NULL,
        symbol TEXT NOT NULL,
        
        future_oi_category TEXT,
        depth_bias TEXT,
        index_bias TEXT,
        sector_bias TEXT,
        market_bias TEXT,
        
        regime TEXT,
        vix_state TEXT,
        
        confidence INTEGER,
        recommended_action TEXT,
        
        metadata TEXT
    )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts_final(time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts_final(symbol)")
    
    conn.commit()
    return conn

# =====================================================
# DATA READERS
# =====================================================

def get_latest_analytics(symbol: str, time: str) -> Optional[dict]:
    """Get latest analytics for symbol"""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get token for symbol
        token = None
        if symbol == "BANKNIFTY":
            token = 12601346
        elif symbol == "NIFTY":
            token = 12602626
        
        if not token:
            return None
        
        cur.execute("""
            SELECT * FROM minute_analytics
            WHERE instrument_token = ? AND time_minute = ?
        """, (token, time))
        
        row = cur.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"[ANALYTICS READ ERR] {e}")
        return None

def get_oi_category(token: int, time: str) -> str:
    """Get OI category for futures"""
    if token not in FUTURE_TOKENS:
        return "NA"
    
    try:
        conn = sqlite3.connect(OI_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT oi_category FROM oi_category_1m
            WHERE instrument_token = ? AND time_minute = ?
        """, (token, time))
        
        row = cur.fetchone()
        conn.close()
        
        return row["oi_category"] if row else "NA"
    except Exception as e:
        print(f"[OI READ ERR] {e}")
        return "NA"

def get_sector_analysis(time: str) -> Dict[str, dict]:
    """Get sector analysis"""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM sector_analytics
            WHERE time_minute = ?
        """, (time,))
        
        rows = cur.fetchall()
        conn.close()
        
        return {row["sector_name"]: dict(row) for row in rows}
    except Exception as e:
        print(f"[SECTOR READ ERR] {e}")
        return {}

def get_market_direction(time: str) -> Optional[dict]:
    """Get market direction"""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM market_direction
            WHERE time_minute = ?
        """, (time,))
        
        row = cur.fetchone()
        conn.close()
        
        return dict(row) if row else None
    except Exception as e:
        print(f"[MARKET READ ERR] {e}")
        return None

# =====================================================
# CONFIDENCE ENGINE
# =====================================================

def calculate_confidence(
    oi_category: str,
    depth_bias: DepthBias,
    sector_bias: str,
    index_bias: str,
    regime: MarketRegime,
    vix_state: VixState
) -> int:
    """
    Calculate 0-100 confidence score
    
    Weights:
    - OI + Depth → 40 points
    - Sector alignment → 30 points
    - Index alignment → 20 points
    - Regime + VIX → 10 points
    """
    score = 0
    
    # Component 1: OI + Depth (40 points)
    oi_bullish = oi_category in ["LB", "SC"]
    oi_bearish = oi_category in ["SB", "LU"]
    depth_bullish = depth_bias == DepthBias.BUYER_DOMINANT
    depth_bearish = depth_bias == DepthBias.SELLER_DOMINANT
    
    if (oi_bullish and depth_bullish) or (oi_bearish and depth_bearish):
        score += 40  # Perfect alignment
    elif oi_bullish or oi_bearish or depth_bullish or depth_bearish:
        score += 20  # Partial signal
    
    # Component 2: Sector (30 points)
    if sector_bias == "BULLISH" and (oi_bullish or depth_bullish):
        score += 30
    elif sector_bias == "BEARISH" and (oi_bearish or depth_bearish):
        score += 30
    elif sector_bias == "NEUTRAL":
        score += 15
    
    # Component 3: Index (20 points)
    if index_bias == "BULLISH" and (oi_bullish or depth_bullish):
        score += 20
    elif index_bias == "BEARISH" and (oi_bearish or depth_bearish):
        score += 20
    elif index_bias == "MIXED":
        score += 10
    
    # Component 4: Regime + VIX (10 points)
    if regime == MarketRegime.TRENDING_UP and (oi_bullish or depth_bullish):
        score += 5
    elif regime == MarketRegime.TRENDING_DOWN and (oi_bearish or depth_bearish):
        score += 5
    
    if vix_state in [VixState.LOW, VixState.NORMAL]:
        score += 5
    elif vix_state == VixState.HIGH:
        score += 2
    
    return min(100, max(0, score))

# =====================================================
# ACTION MAPPER
# =====================================================

def map_action(
    oi_category: str,
    depth_bias: DepthBias,
    regime: MarketRegime,
    vix_state: VixState,
    confidence: int
) -> Action:
    """Map context to trading action"""
    
    if confidence < MIN_CONFIDENCE:
        return Action.NO_TRADE
    
    if vix_state == VixState.EXTREME:
        return Action.WAIT
    
    bullish = oi_category in ["LB", "SC"] or depth_bias == DepthBias.BUYER_DOMINANT
    bearish = oi_category in ["SB", "LU"] or depth_bias == DepthBias.SELLER_DOMINANT
    
    if regime == MarketRegime.TRENDING_UP and bullish:
        return Action.BUY_CE
    elif regime == MarketRegime.TRENDING_DOWN and bearish:
        return Action.BUY_PE
    elif regime == MarketRegime.RANGING:
        if bullish:
            return Action.SELL_PE_PREMIUM
        elif bearish:
            return Action.SELL_CE_PREMIUM
        else:
            return Action.WAIT
    elif regime == MarketRegime.HIGH_VOLATILITY:
        return Action.WAIT
    
    return Action.NO_TRADE

# =====================================================
# MAIN ALERT ENGINE
# =====================================================

def process_alert(time_str: str, alert_conn) -> None:
    """Main alert generation logic"""
    
    # Process BANKNIFTY_FUT
    for fut_token, fut_name in FUTURE_TOKENS.items():
        symbol = fut_name.replace("_FUT", "")
        
        # 1. Get analytics
        analytics = get_latest_analytics(symbol, time_str)
        if not analytics:
            continue
        
        # 2. ANCHOR: OI Category
        oi_category = get_oi_category(fut_token, time_str)
        
        # 3. TRIGGER: Depth Analysis
        bid_ask_ratio = analytics.get('bid_ask_ratio', 1.0)
        order_imbalance = analytics.get('order_imbalance', 0)
        
        if bid_ask_ratio >= BID_ASK_BUY_THRESHOLD and order_imbalance >= ORDER_IMBALANCE_THRESHOLD:
            depth_bias = DepthBias.BUYER_DOMINANT
        elif bid_ask_ratio <= BID_ASK_SELL_THRESHOLD and order_imbalance <= -ORDER_IMBALANCE_THRESHOLD:
            depth_bias = DepthBias.SELLER_DOMINANT
        else:
            depth_bias = DepthBias.NEUTRAL
        
        # Skip if no signal
        if oi_category == "NA" and depth_bias == DepthBias.NEUTRAL:
            continue
        
        # 4. CONFIRMATION: Sector
        sectors = get_sector_analysis(time_str)
        banking = sectors.get("BANKING", {})
        nbfc = sectors.get("NBFC", {})
        
        banking_signal = banking.get("signal", "NEUTRAL")
        nbfc_signal = nbfc.get("signal", "NEUTRAL")
        
        sector_bias = banking_signal if banking_signal == nbfc_signal else "MIXED"
        
        # 5. CONFIRMATION: Index (simplified - use analytics)
        index_bias = "BULLISH" if analytics.get('bullish_percentage', 0) > 60 else \
                     "BEARISH" if analytics.get('bearish_percentage', 0) > 60 else "MIXED"
        
        # 6. CONTEXT: Regime
        regime_str = analytics.get('market_regime', 'RANGING')
        try:
            regime = MarketRegime[regime_str]
        except:
            regime = MarketRegime.RANGING
        
        # 7. CONTEXT: VIX
        vix_value = analytics.get('vix_value', 15.0)
        if vix_value < LOW_VIX:
            vix_state = VixState.LOW
        elif vix_value < 15:
            vix_state = VixState.NORMAL
        elif vix_value < HIGH_VIX:
            vix_state = VixState.HIGH
        else:
            vix_state = VixState.EXTREME
        
        # 8. CONFIDENCE SCORE
        confidence = calculate_confidence(
            oi_category, depth_bias, sector_bias, index_bias, regime, vix_state
        )
        
        # 9. ONE-CANDLE-ONE-DECISION: Check if already alerted
        cur = alert_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM alerts_final
            WHERE symbol = ? AND time = ?
        """, (symbol, time_str))
        
        if cur.fetchone()[0] > 0:
            continue  # Already alerted
        
        # 10. THRESHOLD CHECK
        if confidence < MIN_CONFIDENCE:
            continue
        
        # 11. ACTION MAPPING
        action = map_action(oi_category, depth_bias, regime, vix_state, confidence)
        
        if action == Action.NO_TRADE:
            continue
        
        # 12. WRITE ALERT
        market_bias = f"Banking:{banking_signal}|NBFC:{nbfc_signal}"
        
        cur.execute("""
            INSERT INTO alerts_final
            (time, symbol, future_oi_category, depth_bias, index_bias,
             sector_bias, market_bias, regime, vix_state, confidence, recommended_action)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            time_str, symbol,
            oi_category, depth_bias.value, index_bias,
            sector_bias, market_bias, regime.value, vix_state.value,
            confidence, action.value
        ))
        
        alert_conn.commit()
        
        print(f"✅ ALERT: {symbol} | {oi_category} | {action.value} | Conf:{confidence}")

# =====================================================
# MAIN LOOP
# =====================================================

def main():
    print("🚀 Professional Alert Engine v1.0 Started")
    print("📊 Mode: Context-Aware Market Decision System")
    
    alert_conn = init_alert_db()
    
    last_processed_time = None
    
    while True:
        try:
            # Get latest time from analytics
            analytics_conn = sqlite3.connect(ANALYTICS_DB)
            cur = analytics_conn.cursor()
            
            cur.execute("""
                SELECT MAX(time_minute) as latest
                FROM minute_analytics
            """)
            
            row = cur.fetchone()
            analytics_conn.close()
            
            if row and row[0]:
                latest_time = row[0]
                
                # Process if new
                if latest_time != last_processed_time:
                    process_alert(latest_time, alert_conn)
                    last_processed_time = latest_time
            
            time.sleep(60)  # Check every minute
            
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)
    
    alert_conn.close()

if __name__ == "__main__":
    main()
