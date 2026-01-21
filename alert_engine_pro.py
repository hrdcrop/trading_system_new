#!/usr/bin/env python3
"""
PROFESSIONAL ALERT ENGINE v3.0.2 - METADATA PERSISTENCE FIX
Context-Aware Market Decision System

WHAT'S NEW IN v3.0.2 (METADATA PERSISTENCE FIX):
✅ FIX 1: Metadata JSON serialization and storage
✅ FIX 2: Confirmations list capture in MarketContext

WHAT'S NEW IN v3.0.1 (PRODUCTION FIXES):
✅ FIX 1: Metadata serialization to JSON (no schema changes)
✅ FIX 2: Sector bias normalization (BUY/SELL → BULLISH/BEARISH)
✅ FIX 3: Market bias structure improvement (backward compatible)

WHAT'S NEW IN v3.0 (SIGNAL QUALITY UPGRADE):
✅ Regime-aware confidence caps (RANGING=65%, HIGH_VOL=55%)
✅ OI-Depth disagreement penalty (50% confidence reduction)
✅ Alert type classification (TREND_CONTINUATION, REVERSAL_SETUP, RANGE_PLAY)
✅ Regime as decision gate (strict action filtering)
✅ Multi-confirmation rule (requires 2+ signal alignments)
✅ Alert quality tagging (A+/A/B/SKIP - only A+ and A go to Telegram)
✅ Enhanced Telegram messages with WHY THIS ALERT explanation
✅ Smart frequency control (±10 confidence threshold for same signal)

PRESERVED FEATURES FROM v2.3:
✅ Telegram bot integration
✅ Mobile-friendly alerts
✅ Health monitoring
✅ Auto-retry on failure
✅ Cooldown period to reduce noise
✅ Restart-safe state persistence
✅ Upstream depth bias consumption
✅ 2-minute signal confirmation
✅ OI strength weighting (LB/SB vs SC/LU)
✅ Depth strength using weighted ratio

PRESERVED FIXES:
- FIX 1: OI table name: futures_oi_category_1m
- FIX 2: Depth bias from analytics (weighted_bias/bid_ask_bias)
- FIX 3: Persistent state table for restart safety
- FIX 4: Time consistency using minute resolution only
"""

import sqlite3
import time
import requests
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import statistics
from trading_secrets import TELEGRAM_TOKEN, CHAT_ID

# =====================================================
# CONFIG
# =====================================================

CANDLE_DB = "minute_candles.db"
OI_DB = "oi_analysis.db"
ANALYTICS_DB = "market_analytics.db"
ALERT_DB = "alerts_pro.db"

# Telegram Config
TELEGRAM_ENABLED = bool(TELEGRAM_TOKEN and CHAT_ID)

# Future and Index Tokens
FUTURE_TOKENS = {12601346: "BANKNIFTY", 12602626: "NIFTY"}
INDEX_TOKENS = {12601346: "BANKNIFTY", 12602626: "NIFTY"}
BANKING_STOCKS = [341249, 1270529, 779521, 492033, 1510401, 1346049]
NBFC_STOCKS = [12622082, 12621826, 12804354, 12706818, 12628994]
VIX_TOKEN = 264969

# Thresholds
MIN_CONFIDENCE = 60
BID_ASK_BUY_THRESHOLD = 1.5
BID_ASK_SELL_THRESHOLD = 0.67
ORDER_IMBALANCE_THRESHOLD = 100
HIGH_VIX = 18
NORMAL_VIX = 15
LOW_VIX = 12

# Cooldown Config
ALERT_COOLDOWN_MINUTES = 5

# v3.0: Regime confidence caps
REGIME_CONFIDENCE_CAPS = {
    "TRENDING_UP": 100,
    "TRENDING_DOWN": 100,
    "RANGING": 65,
    "HIGH_VOLATILITY": 55
}

# v3.0: Regime confidence scaling
REGIME_CONFIDENCE_SCALE = {
    "TRENDING_UP": 1.0,
    "TRENDING_DOWN": 1.0,
    "RANGING": 0.85,
    "HIGH_VOLATILITY": 0.7
}

# v3.0: Smart frequency control threshold
CONFIDENCE_CHANGE_THRESHOLD = 10

# v3.0: Alert quality thresholds
ALERT_QUALITY_THRESHOLDS = {
    "A+": 80,
    "A": 70,
    "B": 60
}

# =====================================================
# COOLDOWN STATE
# =====================================================

alert_cooldown_state = {}
pending_signal_state = {}


def is_in_cooldown(symbol: str, action: str, current_time_str: str, current_confidence: int = 0) -> bool:
    """Check if an alert should be suppressed due to cooldown."""
    if symbol not in alert_cooldown_state:
        return False

    state = alert_cooldown_state[symbol]
    last_time_str = state.get("last_alert_time")
    last_action = state.get("last_alert_action")
    last_confidence = state.get("last_alert_confidence", 0)

    if not last_time_str or not last_action:
        return False

    if last_action != action:
        return False

    try:
        current_minute = current_time_str[:16]
        last_minute = last_time_str[:16]

        current_time = datetime.strptime(current_minute, "%Y-%m-%d %H:%M")
        last_time = datetime.strptime(last_minute, "%Y-%m-%d %H:%M")

        elapsed_minutes = (current_time - last_time).total_seconds() / 60

        if elapsed_minutes < ALERT_COOLDOWN_MINUTES:
            confidence_delta = abs(current_confidence - last_confidence)
            if confidence_delta >= CONFIDENCE_CHANGE_THRESHOLD:
                print(f"🔓 FREQUENCY OVERRIDE: {symbol} | Conf Δ={confidence_delta:+d} (≥{CONFIDENCE_CHANGE_THRESHOLD})")
                return False
            return True

    except ValueError as e:
        print(f"[COOLDOWN] Timestamp parse error: {e}")
        return False

    return False


def update_cooldown_state(symbol: str, action: str, time_str: str, confidence: int = 0) -> None:
    """Update cooldown state after an alert is fired."""
    alert_cooldown_state[symbol] = {
        "last_alert_time": time_str[:16],
        "last_alert_action": action,
        "last_alert_confidence": confidence
    }


def get_cooldown_status() -> Dict:
    """Get current cooldown state for debugging/monitoring."""
    return alert_cooldown_state.copy()


# =====================================================
# 2-MINUTE SIGNAL CONFIRMATION
# =====================================================

def check_signal_confirmation(symbol: str, action: str, time_str: str) -> bool:
    """2-minute confirmation to reduce false alerts."""
    global pending_signal_state

    current_minute = time_str[:16]

    if symbol not in pending_signal_state:
        pending_signal_state[symbol] = {
            "pending_action": action,
            "pending_time": current_minute
        }
        print(f"⏳ PENDING: {symbol} | {action} | Awaiting 2-min confirmation...")
        return False

    state = pending_signal_state[symbol]
    pending_action = state.get("pending_action")
    pending_time = state.get("pending_time")

    try:
        current_dt = datetime.strptime(current_minute, "%Y-%m-%d %H:%M")
        pending_dt = datetime.strptime(pending_time, "%Y-%m-%d %H:%M")
        elapsed = (current_dt - pending_dt).total_seconds() / 60
    except ValueError:
        pending_signal_state.pop(symbol, None)
        return False

    if pending_action == action and 0 < elapsed <= 2:
        print(f"✅ CONFIRMED: {symbol} | {action} | 2-min confirmation passed")
        pending_signal_state.pop(symbol, None)
        return True

    if pending_action != action or elapsed > 2:
        pending_signal_state[symbol] = {
            "pending_action": action,
            "pending_time": current_minute
        }
        if pending_action != action:
            print(f"🔄 SIGNAL RESET: {symbol} | {pending_action}→{action}")
        elif elapsed > 2:
            print(f"🔄 TIMEOUT RESET: {symbol} | {action} | Gap: {elapsed:.0f}min")
        return False

    return False


def get_pending_status() -> Dict:
    """Get current pending signal state for debugging."""
    return pending_signal_state.copy()


# =====================================================
# OI STRENGTH WEIGHTING
# =====================================================

def get_oi_weight(oi_category: str) -> float:
    """Return OI contribution weight based on category strength."""
    if oi_category in ["LB", "SB"]:
        return 1.0
    elif oi_category in ["SC", "LU"]:
        return 0.6
    else:
        return 1.0


# =====================================================
# DEPTH STRENGTH USING WEIGHTED RATIO
# =====================================================

def get_depth_strength(analytics: dict) -> Tuple[str, float]:
    """Classify depth strength using weighted_bid_ask_ratio."""
    weighted_ratio = analytics.get('weighted_bid_ask_ratio')

    if weighted_ratio is None:
        return ("UNKNOWN", 1.0)

    if weighted_ratio > 2.0:
        return ("STRONG_BUYER", 1.2)
    elif weighted_ratio >= 1.2:
        return ("BUYER", 1.0)
    elif weighted_ratio >= 0.8:
        return ("NEUTRAL", 0.8)
    elif weighted_ratio >= 0.5:
        return ("SELLER", 1.0)
    else:
        return ("STRONG_SELLER", 1.2)


# =====================================================
# SECTOR BIAS NORMALIZATION
# =====================================================

def normalize_sector_signal(signal: str) -> str:
    """Normalize sector signals to match alert engine expectations."""
    signal_upper = signal.upper()
    
    if signal_upper == "BUY":
        return "BULLISH"
    elif signal_upper == "SELL":
        return "BEARISH"
    elif signal_upper == "NEUTRAL":
        return "NEUTRAL"
    else:
        return "NEUTRAL"


# =====================================================
# MARKET BIAS STRUCTURE IMPROVEMENT
# =====================================================

def derive_overall_market_bias(banking_signal: str, nbfc_signal: str) -> str:
    """Derive overall market bias from sector signals."""
    banking_norm = normalize_sector_signal(banking_signal)
    nbfc_norm = normalize_sector_signal(nbfc_signal)
    
    if banking_norm == nbfc_norm:
        return banking_norm
    else:
        return "MIXED"


def format_market_bias(overall_bias: str, banking_signal: str, nbfc_signal: str) -> str:
    """Format market bias string for backward compatibility."""
    return f"{overall_bias}|Banking:{banking_signal}|NBFC:{nbfc_signal}"


# =====================================================
# TELEGRAM INTEGRATION
# =====================================================

def send_telegram(message: str, priority: str = "NORMAL"):
    """Send alert to Telegram with emoji formatting"""
    if not TELEGRAM_ENABLED:
        print(f"[CONSOLE] {message}")
        return

    try:
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

class AlertType(Enum):
    TREND_CONTINUATION = "TREND_CONTINUATION"
    REVERSAL_SETUP = "REVERSAL_SETUP"
    RANGE_PLAY = "RANGE_PLAY"
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
    alert_type: str = "NO_TRADE"
    alert_quality: str = "SKIP"
    why_explanation: str = ""
    confirmations: List[str] = field(default_factory=list)  # FIX v3.0.2


# =====================================================
# DATABASE SETUP
# =====================================================

def init_alert_db():
    """Initialize alert database with alerts table and state table."""
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

    try:
        cur.execute("ALTER TABLE alerts_final ADD COLUMN telegram_sent INTEGER DEFAULT 0")
        print("✅ Added telegram_sent column to existing table")
    except sqlite3.OperationalError:
        pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS alert_state (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts_final(time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts_final(symbol)")

    conn.commit()
    return conn


# =====================================================
# STATE PERSISTENCE FUNCTIONS
# =====================================================

def get_last_processed_time(conn) -> Optional[str]:
    """Load last processed time from persistent state."""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT value FROM alert_state WHERE key = 'last_processed_time'
        """)
        row = cur.fetchone()
        cur.close()

        if row and row[0]:
            return row[0]
        return None
    except Exception as e:
        print(f"[STATE READ ERR] {e}")
        return None


def set_last_processed_time(conn, time_str: str) -> None:
    """Persist last processed time to state table."""
    try:
        cur = conn.cursor()
        time_minute = time_str[:16]
        cur.execute("""
            INSERT OR REPLACE INTO alert_state (key, value)
            VALUES ('last_processed_time', ?)
        """, (time_minute,))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"[STATE WRITE ERR] {e}")


# =====================================================
# DATA READERS
# =====================================================

def get_latest_analytics(symbol: str, time_minute: str) -> Optional[dict]:
    """Get latest analytics for symbol."""
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
            conn.close()
            return None

        cur.execute("""
            SELECT * FROM minute_analytics
            WHERE instrument_token = ? AND time_minute = ?
        """, (token, time_minute))

        row = cur.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"[ANALYTICS READ ERR] {e}")
        return None


def get_oi_category(token: int, time_minute: str) -> str:
    """Get OI category for futures."""
    if token not in FUTURE_TOKENS:
        return "NA"

    try:
        conn = sqlite3.connect(OI_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT oi_category FROM futures_oi_category_1m
            WHERE instrument_token = ? AND time_minute = ?
        """, (token, time_minute))

        row = cur.fetchone()
        conn.close()

        return row["oi_category"] if row else "NA"
    except Exception as e:
        print(f"[OI READ ERR] {e}")
        return "NA"


def get_sector_analysis(time_minute: str) -> Dict[str, dict]:
    """Get sector analysis for given minute."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM sector_analytics
            WHERE time_minute = ?
        """, (time_minute,))

        rows = cur.fetchall()
        conn.close()

        return {row["sector_name"]: dict(row) for row in rows}
    except Exception as e:
        print(f"[SECTOR READ ERR] {e}")
        return {}


def get_market_direction(time_minute: str) -> Optional[dict]:
    """Get market direction for given minute."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM market_direction
            WHERE time_minute = ?
        """, (time_minute,))

        row = cur.fetchone()
        conn.close()

        return dict(row) if row else None
    except Exception as e:
        print(f"[MARKET READ ERR] {e}")
        return None


# =====================================================
# DEPTH BIAS FROM UPSTREAM ANALYTICS
# =====================================================

def get_depth_bias_from_analytics(analytics: dict) -> DepthBias:
    """Read depth bias from analytics row instead of recalculating."""
    weighted_bias = analytics.get('weighted_bias')
    if weighted_bias:
        if weighted_bias == "BUYER_DOMINANT":
            return DepthBias.BUYER_DOMINANT
        elif weighted_bias == "SELLER_DOMINANT":
            return DepthBias.SELLER_DOMINANT
        elif weighted_bias == "NEUTRAL":
            return DepthBias.NEUTRAL

    bid_ask_bias = analytics.get('bid_ask_bias')
    if bid_ask_bias:
        if bid_ask_bias == "BUYER_DOMINANT":
            return DepthBias.BUYER_DOMINANT
        elif bid_ask_bias == "SELLER_DOMINANT":
            return DepthBias.SELLER_DOMINANT
        elif bid_ask_bias == "NEUTRAL":
            return DepthBias.NEUTRAL

    return DepthBias.NEUTRAL


# =====================================================
# v3.0: CONFIDENCE ENGINE (UPGRADED)
# =====================================================

def calculate_confidence(
    oi_category: str,
    depth_bias: DepthBias,
    sector_bias: str,
    index_bias: str,
    regime: MarketRegime,
    vix_state: VixState,
    analytics: dict = None
) -> int:
    """Calculate 0-100 confidence score."""
    score = 0

    oi_weight = get_oi_weight(oi_category)

    depth_strength_label, depth_multiplier = ("UNKNOWN", 1.0)
    if analytics:
        depth_strength_label, depth_multiplier = get_depth_strength(analytics)

    oi_bullish = oi_category in ["LB", "SC"]
    oi_bearish = oi_category in ["SB", "LU"]
    depth_bullish = depth_bias == DepthBias.BUYER_DOMINANT
    depth_bearish = depth_bias == DepthBias.SELLER_DOMINANT

    oi_depth_agree = False
    
    oi_depth_points = 0
    if (oi_bullish and depth_bullish) or (oi_bearish and depth_bearish):
        oi_depth_points = 40
        oi_depth_agree = True
    elif oi_bullish or oi_bearish or depth_bullish or depth_bearish:
        oi_depth_points = 20

    oi_depth_points = int(oi_depth_points * oi_weight)
    oi_depth_points = int(oi_depth_points * depth_multiplier)

    score += oi_depth_points

    if sector_bias == "BULLISH" and (oi_bullish or depth_bullish):
        score += 30
    elif sector_bias == "BEARISH" and (oi_bearish or depth_bearish):
        score += 30
    elif sector_bias == "NEUTRAL":
        score += 15

    if index_bias == "BULLISH" and (oi_bullish or depth_bullish):
        score += 20
    elif index_bias == "BEARISH" and (oi_bearish or depth_bearish):
        score += 20
    elif index_bias == "MIXED":
        score += 10

    if regime == MarketRegime.TRENDING_UP and (oi_bullish or depth_bullish):
        score += 5
    elif regime == MarketRegime.TRENDING_DOWN and (oi_bearish or depth_bearish):
        score += 5

    if vix_state in [VixState.LOW, VixState.NORMAL]:
        score += 5
    elif vix_state == VixState.HIGH:
        score += 2

    if not oi_depth_agree and oi_category != "NA":
        if (oi_bullish and depth_bearish) or (oi_bearish and depth_bullish):
            score = int(score * 0.5)
            print(f"⚠️ OI-DEPTH CONFLICT: Confidence reduced by 50% (OI:{oi_category}, Depth:{depth_bias.value})")

    regime_scale = REGIME_CONFIDENCE_SCALE.get(regime.value, 1.0)
    score = int(score * regime_scale)

    regime_cap = REGIME_CONFIDENCE_CAPS.get(regime.value, 100)
    if score > regime_cap:
        original_score = score
        score = regime_cap
        print(f"🔒 REGIME CAP: {regime.value} limited confidence {original_score}→{score}")

    return min(100, max(0, score))


# =====================================================
# v3.0: ALERT TYPE CLASSIFICATION
# =====================================================

def classify_alert_type(
    oi_category: str,
    depth_bias: DepthBias,
    regime: MarketRegime,
    sector_bias: str,
    index_bias: str
) -> AlertType:
    """Classify alert into professional trading scenarios."""
    oi_bullish = oi_category in ["LB", "SC"]
    oi_bearish = oi_category in ["SB", "LU"]
    depth_bullish = depth_bias == DepthBias.BUYER_DOMINANT
    depth_bearish = depth_bias == DepthBias.SELLER_DOMINANT

    bullish_signal = oi_bullish or depth_bullish
    bearish_signal = oi_bearish or depth_bearish

    if regime == MarketRegime.RANGING:
        return AlertType.RANGE_PLAY

    if regime == MarketRegime.TRENDING_UP and bullish_signal:
        return AlertType.TREND_CONTINUATION
    elif regime == MarketRegime.TRENDING_DOWN and bearish_signal:
        return AlertType.TREND_CONTINUATION

    if regime == MarketRegime.TRENDING_UP and bearish_signal:
        return AlertType.REVERSAL_SETUP
    elif regime == MarketRegime.TRENDING_DOWN and bullish_signal:
        return AlertType.REVERSAL_SETUP

    return AlertType.NO_TRADE


# =====================================================
# v3.0: MULTI-CONFIRMATION RULE
# =====================================================

def check_multi_confirmation(
    oi_category: str,
    depth_bias: DepthBias,
    sector_bias: str,
    index_bias: str,
    regime: MarketRegime
) -> Tuple[bool, List[str]]:
    """Require at least 2 confirmations from different sources."""
    confirmations = []

    oi_bullish = oi_category in ["LB", "SC"]
    oi_bearish = oi_category in ["SB", "LU"]
    depth_bullish = depth_bias == DepthBias.BUYER_DOMINANT
    depth_bearish = depth_bias == DepthBias.SELLER_DOMINANT

    if (oi_bullish and depth_bullish) or (oi_bearish and depth_bearish):
        confirmations.append("OI+Depth")

    if sector_bias in ["BULLISH", "BEARISH"]:
        confirmations.append("Sector")

    if index_bias in ["BULLISH", "BEARISH"]:
        confirmations.append("Index")

    if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
        confirmations.append("Regime")

    passed = len(confirmations) >= 2

    return (passed, confirmations)


# =====================================================
# v3.0: ALERT QUALITY GRADING
# =====================================================

def grade_alert_quality(confidence: int) -> str:
    """Grade alert quality based on confidence."""
    if confidence >= ALERT_QUALITY_THRESHOLDS["A+"]:
        return "A+"
    elif confidence >= ALERT_QUALITY_THRESHOLDS["A"]:
        return "A"
    elif confidence >= ALERT_QUALITY_THRESHOLDS["B"]:
        return "B"
    else:
        return "SKIP"


# =====================================================
# v3.0: WHY EXPLANATION GENERATOR
# =====================================================

def generate_why_explanation(
    oi_category: str,
    depth_bias: DepthBias,
    sector_bias: str,
    index_bias: str,
    regime: MarketRegime,
    alert_type: AlertType,
    confirmations: List[str]
) -> str:
    """Generate human-readable explanation for why this alert was triggered."""
    parts = []

    if alert_type == AlertType.TREND_CONTINUATION:
        parts.append("Trend continuation setup")
    elif alert_type == AlertType.REVERSAL_SETUP:
        parts.append("Potential reversal setup")
    elif alert_type == AlertType.RANGE_PLAY:
        parts.append("Range-bound play")

    if confirmations:
        parts.append(f"Confirmations: {', '.join(confirmations)}")

    if oi_category != "NA":
        parts.append(f"OI:{oi_category}")
    parts.append(f"Depth:{depth_bias.value}")

    parts.append(f"Regime:{regime.value}")

    return " | ".join(parts)


# =====================================================
# DECISION ENGINE
# =====================================================

def decide_action(
    oi_category: str,
    depth_bias: DepthBias,
    sector_bias: str,
    index_bias: str,
    regime: MarketRegime,
    vix_state: VixState
) -> Tuple[Action, str]:
    """Decide trading action with regime-aware filtering."""
    oi_bullish = oi_category in ["LB", "SC"]
    oi_bearish = oi_category in ["SB", "LU"]
    depth_bullish = depth_bias == DepthBias.BUYER_DOMINANT
    depth_bearish = depth_bias == DepthBias.SELLER_DOMINANT

    bullish_signals = sum([oi_bullish, depth_bullish,
                           sector_bias == "BULLISH",
                           index_bias == "BULLISH"])
    bearish_signals = sum([oi_bearish, depth_bearish,
                           sector_bias == "BEARISH",
                           index_bias == "BEARISH"])

    if regime == MarketRegime.HIGH_VOLATILITY:
        return (Action.WAIT, "High volatility - avoid new positions")

    if regime == MarketRegime.RANGING:
        if bullish_signals >= 2:
            return (Action.SELL_PE_PREMIUM, "Range play - sell puts")
        elif bearish_signals >= 2:
            return (Action.SELL_CE_PREMIUM, "Range play - sell calls")
        else:
            return (Action.WAIT, "Ranging - no clear edge")

    if regime == MarketRegime.TRENDING_UP:
        if bullish_signals >= 2:
            return (Action.BUY_CE, "Trend continuation - buy calls")
        elif bearish_signals >= 2:
            return (Action.BUY_PE, "Potential reversal - buy puts")
        else:
            return (Action.WAIT, "Trending up - waiting for signal")

    if regime == MarketRegime.TRENDING_DOWN:
        if bearish_signals >= 2:
            return (Action.BUY_PE, "Trend continuation - buy puts")
        elif bullish_signals >= 2:
            return (Action.BUY_CE, "Potential reversal - buy calls")
        else:
            return (Action.WAIT, "Trending down - waiting for signal")

    return (Action.NO_TRADE, "No clear setup")


# =====================================================
# REGIME DETECTION
# =====================================================

def detect_regime(analytics: dict) -> MarketRegime:
    """Detect market regime from analytics."""
    regime_str = analytics.get('market_regime') or analytics.get('regime', 'UNKNOWN')

    if regime_str == "TRENDING_UP":
        return MarketRegime.TRENDING_UP
    elif regime_str == "TRENDING_DOWN":
        return MarketRegime.TRENDING_DOWN
    elif regime_str == "RANGING":
        return MarketRegime.RANGING
    elif regime_str == "HIGH_VOLATILITY":
        return MarketRegime.HIGH_VOLATILITY
    else:
        return MarketRegime.RANGING


def detect_vix_state(analytics: dict) -> VixState:
    """Detect VIX state from analytics."""
    vix_close = analytics.get('vix_value') or analytics.get('vix_close')

    if vix_close is None:
        return VixState.NORMAL

    if vix_close > 25:
        return VixState.EXTREME
    elif vix_close > HIGH_VIX:
        return VixState.HIGH
    elif vix_close > LOW_VIX:
        return VixState.NORMAL
    else:
        return VixState.LOW


# =====================================================
# CORE ALERT GENERATION
# =====================================================

def generate_alert(symbol: str, time_minute: str) -> Optional[MarketContext]:
    """Generate alert for symbol at given time."""
    analytics = get_latest_analytics(symbol, time_minute)
    if not analytics:
        return None

    token = None
    if symbol == "BANKNIFTY":
        token = 12601346
    elif symbol == "NIFTY":
        token = 12602626
    else:
        return None

    oi_category = get_oi_category(token, time_minute)
    depth_bias = get_depth_bias_from_analytics(analytics)

    sectors = get_sector_analysis(time_minute)
    banking_signal = sectors.get("Banking", {}).get("signal", "NEUTRAL")
    nbfc_signal = sectors.get("NBFC", {}).get("signal", "NEUTRAL")

    sector_bias = normalize_sector_signal(banking_signal)
    overall_bias = derive_overall_market_bias(banking_signal, nbfc_signal)
    market_bias = format_market_bias(overall_bias, banking_signal, nbfc_signal)

    market_dir = get_market_direction(time_minute)
    index_bias = market_dir.get("direction", "MIXED") if market_dir else "MIXED"

    regime = detect_regime(analytics)
    vix_state = detect_vix_state(analytics)

    confirmation_passed, confirmations = check_multi_confirmation(
        oi_category, depth_bias, sector_bias, index_bias, regime
    )

    if not confirmation_passed:
        print(f"❌ MULTI-CONF FAILED: {symbol} | Only {len(confirmations)} confirmations")
        return None

    confidence = calculate_confidence(
        oi_category, depth_bias, sector_bias, index_bias,
        regime, vix_state, analytics
    )

    if confidence < MIN_CONFIDENCE:
        return None

    alert_quality = grade_alert_quality(confidence)

    if alert_quality == "SKIP":
        return None

    alert_type = classify_alert_type(
        oi_category, depth_bias, regime, sector_bias, index_bias
    )

    action, reasoning = decide_action(
        oi_category, depth_bias, sector_bias, index_bias,
        regime, vix_state
    )

    if action in [Action.NO_TRADE, Action.WAIT]:
        return None

    why_explanation = generate_why_explanation(
        oi_category, depth_bias, sector_bias, index_bias,
        regime, alert_type, confirmations
    )

    # FIX v3.0.2: confirmation storage
    context = MarketContext(
        time=time_minute,
        symbol=symbol,
        future_oi=oi_category,
        depth_bias=depth_bias.value,
        index_bias=index_bias,
        sector_bias=sector_bias,
        market_bias=market_bias,
        regime=regime.value,
        vix_state=vix_state.value,
        confidence=confidence,
        action=action.value,
        alert_type=alert_type.value,
        alert_quality=alert_quality,
        why_explanation=why_explanation,
        confirmations=confirmations
    )

    return context


# =====================================================
# ALERT PERSISTENCE
# =====================================================

def save_alert(conn, context: MarketContext) -> bool:
    """Save alert to database."""
    try:
        cur = conn.cursor()

        # FIX v3.0.2: metadata persistence
        metadata = {
            "alert_type": context.alert_type,
            "alert_quality": context.alert_quality,
            "why": context.why_explanation,
            "confirmations": context.confirmations
        }
        metadata_json = json.dumps(metadata)

        cur.execute("""
            INSERT INTO alerts_final (
                time, symbol,
                future_oi_category, depth_bias, index_bias,
                sector_bias, market_bias,
                regime, vix_state,
                confidence, recommended_action,
                metadata, telegram_sent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            context.time, context.symbol,
            context.future_oi, context.depth_bias, context.index_bias,
            context.sector_bias, context.market_bias,
            context.regime, context.vix_state,
            context.confidence, context.action,
            metadata_json
        ))

        conn.commit()
        cur.close()
        return True

    except Exception as e:
        print(f"[SAVE ERR] {e}")
        return False


# =====================================================
# TELEGRAM ALERT FORMATTING
# =====================================================

def format_telegram_alert(context: MarketContext) -> str:
    """Enhanced Telegram message with WHY explanation."""
    quality_emoji = {
        "A+": "🟢",
        "A": "🔵",
        "B": "🟡"
    }
    emoji = quality_emoji.get(context.alert_quality, "⚪")

    action_emoji = {
        "BUY_CE": "📈",
        "BUY_PE": "📉",
        "SELL_CE_PREMIUM": "💰",
        "SELL_PE_PREMIUM": "💰"
    }
    act_emoji = action_emoji.get(context.action, "📊")

    message = f"""{emoji} <b>{context.alert_quality} GRADE ALERT</b>

{act_emoji} <b>{context.symbol}</b> | {context.action.replace('_', ' ')}
⏰ {context.time}

<b>📊 CONFIDENCE: {context.confidence}%</b>

<b>🎯 WHY THIS ALERT:</b>
{context.why_explanation}

<b>📈 MARKET CONTEXT:</b>
• OI: {context.future_oi}
• Depth: {context.depth_bias}
• Sector: {context.sector_bias}
• Index: {context.index_bias}
• Regime: {context.regime}
• VIX: {context.vix_state}

<b>🏷️ Type:</b> {context.alert_type.replace('_', ' ')}"""

    return message


# =====================================================
# MAIN ALERT PROCESSOR
# =====================================================

def process_alerts(conn):
    """Main alert processing loop."""
    last_processed = get_last_processed_time(conn)

    try:
        analytics_conn = sqlite3.connect(ANALYTICS_DB)
        cur = analytics_conn.cursor()
        cur.execute("SELECT MAX(time_minute) FROM minute_analytics")
        row = cur.fetchone()
        analytics_conn.close()

        if not row or not row[0]:
            print("[NO DATA] No analytics data available")
            return

        latest_time = row[0]

    except Exception as e:
        print(f"[ANALYTICS TIME ERR] {e}")
        return

    if last_processed and latest_time <= last_processed:
        print(f"[SKIP] Already processed {latest_time}")
        return

    print(f"\n{'='*60}")
    print(f"🔍 PROCESSING: {latest_time}")
    print(f"{'='*60}\n")

    for symbol in ["BANKNIFTY", "NIFTY"]:
        print(f"\n--- {symbol} ---")

        context = generate_alert(symbol, latest_time)

        if not context:
            print(f"✗ No alert for {symbol}")
            continue

        print(f"✓ Alert generated: {context.action} | Conf={context.confidence}% | Quality={context.alert_quality}")

        if not check_signal_confirmation(symbol, context.action, latest_time):
            print(f"⏳ Signal pending confirmation")
            continue

        if is_in_cooldown(symbol, context.action, latest_time, context.confidence):
            print(f"🔇 In cooldown period")
            continue

        if save_alert(conn, context):
            print(f"💾 Saved to database")

            if context.alert_quality in ["A+", "A"]:
                message = format_telegram_alert(context)
                priority = "HIGH" if context.alert_quality == "A+" else "MEDIUM"
                send_telegram(message, priority)

                update_cooldown_state(symbol, context.action, latest_time, context.confidence)
            else:
                print(f"📋 Quality {context.alert_quality} - logged only (no Telegram)")
        else:
            print(f"❌ Save failed")

    set_last_processed_time(conn, latest_time)
    print(f"\n✅ Processing complete: {latest_time}\n")


# =====================================================
# MAIN LOOP
# =====================================================

def main():
    """Main execution loop."""
    print("="*60)
    print("🚀 ALERT ENGINE PRO v3.0.2 - METADATA PERSISTENCE FIX")
    print("="*60)
    print(f"Telegram: {'✅ ENABLED' if TELEGRAM_ENABLED else '❌ DISABLED'}")
    print(f"Min Confidence: {MIN_CONFIDENCE}%")
    print(f"Cooldown: {ALERT_COOLDOWN_MINUTES} minutes")
    print("="*60)

    conn = init_alert_db()

    try:
        while True:
            try:
                process_alerts(conn)
            except Exception as e:
                print(f"❌ ERROR: {e}")
                import traceback
                traceback.print_exc()

            time.sleep(60)

    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        conn.close()
        print("✅ Database closed")


if __name__ == "__main__":
    main()
