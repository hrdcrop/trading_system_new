#!/usr/bin/env python3
"""
PROFESSIONAL ALERT ENGINE v2.1 - WITH TELEGRAM + COOLDOWN
Context-Aware Market Decision System

FEATURES:
✅ Telegram bot integration
✅ Mobile-friendly alerts
✅ Health monitoring
✅ Auto-retry on failure
✅ Cooldown period to reduce noise (v2.1)
"""



import sqlite3
import time
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import statistics
from secrets import TELEGRAM_TOKEN, CHAT_ID

# =====================================================
# CONFIG
# =====================================================

CANDLE_DB = "minute_candles.db"
OI_DB = "oi_analysis.db"
ANALYTICS_DB = "market_analytics.db"
ALERT_DB = "alerts_pro.db"

# Telegram Config

TELEGRAM_ENABLED = bool(TELEGRAM_TOKEN and CHAT_ID)

# Tokens
FUTURE_TOKENS = {13568258: "BANKNIFTY_FUT", 256265: "NIFTY_FUT"}
INDEX_TOKENS = {12601346: "BANKNIFTY", 12602626: "NIFTY"}
BANKING_STOCKS = [341249, 1270529, 779521, 492033, 1510401, 1346049]
NBFC_STOCKS = [12622082, 12621826, 12804354, 12706818, 12628994]
VIX_TOKEN = 264969

# Thresholds
MIN_CONFIDENCE = 55
BID_ASK_BUY_THRESHOLD = 1.5
BID_ASK_SELL_THRESHOLD = 0.67
ORDER_IMBALANCE_THRESHOLD = 100
HIGH_VIX = 18
NORMAL_VIX = 15
LOW_VIX = 12

# Cooldown Config (v2.1)
ALERT_COOLDOWN_MINUTES = 5

# =====================================================
# COOLDOWN STATE (v2.1)
# =====================================================

# In-memory state to track cooldowns per symbol
# Structure: {symbol: {"last_alert_time": str, "last_alert_action": str}}
alert_cooldown_state = {}


def is_in_cooldown(symbol: str, action: str, current_time_str: str) -> bool:
    """
    Check if an alert should be suppressed due to cooldown.
    
    Returns True if:
    - Same action was fired within ALERT_COOLDOWN_MINUTES
    
    Returns False (allow alert) if:
    - No previous alert for this symbol
    - Previous alert was different action (reversal)
    - Cooldown period has expired
    """
    if symbol not in alert_cooldown_state:
        return False
    
    state = alert_cooldown_state[symbol]
    last_time_str = state.get("last_alert_time")
    last_action = state.get("last_alert_action")
    
    if not last_time_str or not last_action:
        return False
    
    # Different action = reversal, allow immediately
    if last_action != action:
        return False
    
    # Parse timestamps and check cooldown
    try:
        current_time = datetime.strptime(current_time_str, "%Y-%m-%d %H:%M:%S")
        last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
        
        elapsed_minutes = (current_time - last_time).total_seconds() / 60
        
        if elapsed_minutes < ALERT_COOLDOWN_MINUTES:
            return True  # Still in cooldown
        
    except ValueError as e:
        # If timestamp parsing fails, allow the alert
        print(f"[COOLDOWN] Timestamp parse error: {e}")
        return False
    
    return False


def update_cooldown_state(symbol: str, action: str, time_str: str) -> None:
    """
    Update cooldown state after an alert is fired.
    """
    alert_cooldown_state[symbol] = {
        "last_alert_time": time_str,
        "last_alert_action": action
    }


def get_cooldown_status() -> Dict:
    """
    Get current cooldown state for debugging/monitoring.
    """
    return alert_cooldown_state.copy()


# =====================================================
# TELEGRAM INTEGRATION
# =====================================================

def send_telegram(message: str, priority: str = "NORMAL"):
    """Send alert to Telegram with emoji formatting"""
    if not TELEGRAM_ENABLED:
        print(f"[CONSOLE] {message}")
        return
    
    try:
        # Add priority emoji
        if priority == "HIGH":
            message = f"🔴 <b>HIGH PRIORITY</b>\n\n{message}"
        elif priority == "MEDIUM":
            message = f"🟡 <b>ALERT</b>\n\n{message}"
        
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"✅ Telegram sent: {message[:50]}...")
        else:
            print(f"❌ Telegram failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        # Fallback to console
        print(f"[CONSOLE FALLBACK] {message}")

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
        
        metadata TEXT,
        telegram_sent INTEGER DEFAULT 0
    )
    """)
    
    # Migration: Add telegram_sent to existing tables
    try:
        cur.execute("ALTER TABLE alerts_final ADD COLUMN telegram_sent INTEGER DEFAULT 0")
        print("✅ Added telegram_sent column to existing table")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
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
    """Calculate 0-100 confidence score"""
    score = 0
    
    # Component 1: OI + Depth (40 points)
    oi_bullish = oi_category in ["LB", "SC"]
    oi_bearish = oi_category in ["SB", "LU"]
    depth_bullish = depth_bias == DepthBias.BUYER_DOMINANT
    depth_bearish = depth_bias == DepthBias.SELLER_DOMINANT
    
    if (oi_bullish and depth_bullish) or (oi_bearish and depth_bearish):
        score += 40
    elif oi_bullish or oi_bearish or depth_bullish or depth_bearish:
        score += 20
    
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
# TELEGRAM ALERT FORMATTER
# =====================================================

def format_telegram_alert(context: MarketContext) -> str:
    """Format alert for mobile/Telegram"""
    
    # Determine alert type
    if "BUY_CE" in context.action:
        emoji = "🟢"
        action_text = "BUY CALL"
    elif "BUY_PE" in context.action:
        emoji = "🔴"
        action_text = "BUY PUT"
    elif "SELL" in context.action:
        emoji = "🟡"
        action_text = "SELL PREMIUM"
    else:
        emoji = "⚪"
        action_text = "WAIT"
    
    # Build message
    message = f"""
{emoji} <b>{context.symbol}</b> - {context.time[11:16]}

<b>📊 SIGNAL: {action_text}</b>
━━━━━━━━━━━━━━━━

<b>🎯 Confidence: {context.confidence}%</b>

<b>📈 Context:</b>
├ OI: {context.future_oi}
├ Depth: {context.depth_bias}
├ Sector: {context.sector_bias}
├ Market: {context.market_bias}
└ Regime: {context.regime}

<b>💹 VIX:</b> {context.vix_state}

<b>⚡ Action:</b> {context.action}
"""
    
    return message.strip()

# =====================================================
# MAIN ALERT ENGINE
# =====================================================

def process_alert(time_str: str, alert_conn) -> None:
    """Main alert generation logic"""
    
    for fut_token, fut_name in FUTURE_TOKENS.items():
        try:
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
            
            # 5. CONFIRMATION: Index
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
            elif vix_value < NORMAL_VIX:
                vix_state = VixState.NORMAL
            elif vix_value < HIGH_VIX:
                vix_state = VixState.HIGH
            else:
                vix_state = VixState.EXTREME
            
            # 8. CONFIDENCE SCORE
            confidence = calculate_confidence(
                oi_category, depth_bias, sector_bias, index_bias, regime, vix_state
            )
            
            # 9. ONE-CANDLE-ONE-DECISION
            cur = alert_conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM alerts_final
                WHERE symbol = ? AND time = ?
            """, (symbol, time_str))
            
            if cur.fetchone()[0] > 0:
                continue
            
            # 10. THRESHOLD CHECK
            if confidence < MIN_CONFIDENCE:
                continue
            
            # 11. ACTION MAPPING
            action = map_action(oi_category, depth_bias, regime, vix_state, confidence)
            
            if action == Action.NO_TRADE:
                continue
            
            # 12. COOLDOWN CHECK (v2.1)
            # Skip if same action is within cooldown period
            # Reversals (different action) bypass cooldown
            if is_in_cooldown(symbol, action.value, time_str):
                print(f"⏸️ COOLDOWN: {symbol} | {action.value} | Suppressed (same signal within {ALERT_COOLDOWN_MINUTES}min)")
                continue
            
            # 13. CREATE CONTEXT
            market_bias = f"Banking:{banking_signal}|NBFC:{nbfc_signal}"
            
            context = MarketContext(
                time=time_str,
                symbol=symbol,
                future_oi=oi_category,
                depth_bias=depth_bias.value,
                index_bias=index_bias,
                sector_bias=sector_bias,
                market_bias=market_bias,
                regime=regime.value,
                vix_state=vix_state.value,
                confidence=confidence,
                action=action.value
            )
            
            # 14. SEND TO TELEGRAM FIRST
            telegram_msg = format_telegram_alert(context)
            priority = "HIGH" if confidence >= 75 else "MEDIUM"
            send_telegram(telegram_msg, priority)
            
            # 15. UPDATE COOLDOWN STATE (v2.1)
            update_cooldown_state(symbol, action.value, time_str)
            
            # 16. WRITE TO DATABASE (with telegram status)
            telegram_status = 1 if TELEGRAM_ENABLED else 0
            
            cur.execute("""
                INSERT INTO alerts_final
                (time, symbol, future_oi_category, depth_bias, index_bias,
                 sector_bias, market_bias, regime, vix_state, confidence, 
                 recommended_action, telegram_sent)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                context.time, context.symbol,
                context.future_oi, context.depth_bias, context.index_bias,
                context.sector_bias, context.market_bias, context.regime, context.vix_state,
                context.confidence, context.action, telegram_status
            ))
            
            alert_conn.commit()
            
            print(f"✅ ALERT: {symbol} | {oi_category} | {action.value} | Conf:{confidence}")
            
        except Exception as e:
            print(f"[ALERT ERR] {symbol}: {e}")
            import traceback
            traceback.print_exc()
            continue

# =====================================================
# MAIN LOOP
# =====================================================

def main():
    print("🚀 Professional Alert Engine v2.1 Started")
    print("📊 Mode: Context-Aware Market Decision System")
    print(f"📱 Telegram: {'✅ ENABLED' if TELEGRAM_ENABLED else '❌ DISABLED'}")
    print(f"⏱️ Cooldown: {ALERT_COOLDOWN_MINUTES} minutes (same signal)")
    
    # Send startup notification
    if TELEGRAM_ENABLED:
        send_telegram(f"""
🚀 <b>Alert Engine v2.1 Started</b>

✅ System: ONLINE
📊 Mode: Context-Aware
🎯 Min Confidence: {MIN_CONFIDENCE}%
⏱️ Cooldown: {ALERT_COOLDOWN_MINUTES}min

Ready to monitor markets...
""", "MEDIUM")
    
    alert_conn = init_alert_db()
    last_processed_time = None
    error_count = 0
    MAX_ERRORS = 5
    
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
                    error_count = 0  # Reset on success
            
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            if TELEGRAM_ENABLED:
                send_telegram("🛑 <b>Alert Engine Stopped</b>\n\nManual shutdown", "MEDIUM")
            break
            
        except Exception as e:
            error_count += 1
            print(f"❌ Error: {e}")
            
            if error_count >= MAX_ERRORS:
                if TELEGRAM_ENABLED:
                    send_telegram(f"⚠️ <b>Critical Error</b>\n\nEngine crashed: {e}", "HIGH")
                break
            
            time.sleep(5)
    
    alert_conn.close()

if __name__ == "__main__":
    main()
