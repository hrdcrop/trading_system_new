#!/usr/bin/env python3
"""
COMPREHENSIVE ANALYTICS ENGINE - CONTINUOUS MODE (PRODUCTION FIXED)
====================================================================
Calculates 21 indicators + sector analysis + market direction
Saves complete row-based analytics for GUI consumption

Pipeline Position:
    tick_json_saver.py → candle_builder_1m.py → oi_category_builder_v2.py
                                    ↓                      ↓
                              minute_candles.db      oi_analysis.db
                                    ↓                      ↓
                              ════════════════════════════════
                              │  comprehensive_analytics_engine.py  │
                              ════════════════════════════════
                                            ↓
                                    market_analytics.db
                                            ↓
                                    alert_engine_pro.py

Philosophy:
- Every minute, every symbol → One complete row
- Raw data + Calculated indicators + Context
- NO decisions (that's alert engine's job)
- GUI-ready format (charts, tables, heatmaps)
"""

import sqlite3
import time
import statistics
import json
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import pytz

# =====================================================
# CONFIG
# =====================================================

CANDLE_DB = "minute_candles.db"
OI_DB = "oi_analysis.db"
ANALYTICS_DB = "market_analytics.db"

IST = pytz.timezone("Asia/Kolkata")

# Instrument tokens
INDEX_TOKENS = {
    12601346: "BANKNIFTY",
    12602626: "NIFTY",
    12601602: "FINNIFTY"
}

STOCK_TOKENS = {
    341249: "HDFCBANK",
    1270529: "ICICIBANK",
    779521: "SBIN",
    492033: "KOTAKBANK",
    1510401: "AXISBANK",
    1346049: "INDUSINDBK",
    738561: "RELIANCE",
    2714625: "BHARTIARTL",
    2953217: "TCS",
    408065: "INFY"
}

NBFC_TOKENS = {
    12622082: "BAJFINANCE",
    12621826: "BAJAJFINSV",
    12804354: "SHRIRAMFIN",
    12706818: "MUTHOOTFIN",
    12628994: "CHOLAFIN"
}

VIX_TOKEN = 264969
VIX_SYMBOL = "INDIA_VIX"

PROCESSING_TOKENS = {**INDEX_TOKENS, **STOCK_TOKENS, **NBFC_TOKENS}
ALL_TOKENS = {**PROCESSING_TOKENS, VIX_TOKEN: VIX_SYMBOL}

FUTURE_TOKENS = {
    12601346: "BANKNIFTY",
    12602626: "NIFTY"
}

SECTORS = {
    "BANKING": [341249, 1270529, 779521, 492033, 1510401, 1346049],
    "NBFC": list(NBFC_TOKENS.keys()),
    "IT": [2953217, 408065],
    "TELECOM": [2714625],
    "ENERGY": [738561]
}

# Thresholds
BUY_THRESHOLD = 1.5
SELL_THRESHOLD = 0.67
ORDER_IMBALANCE_THRESHOLD = 100
ADX_THRESHOLD = 25
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Signal keys constant for aggregation (OPTIONAL FIX - safer than string duplication)
SIGNAL_KEYS = [
    'ema_9', 'ema_21', 'ema_50', 'ema_200', 'macd', 'adx_trend', 'kalman',
    'rsi', 'stoch', 'cci', 'mfi', 'roc', 'bb', 'atr_trend',
    'vwap', 'volume_trend', 'obv', 'oi', 'depth', 'pattern', 'regime'
]

# =====================================================
# ENUMS
# =====================================================

class MarketRegime(Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"

class VixState(Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

class DepthBias(Enum):
    BUYER_DOMINANT = "BUYER_DOMINANT"
    SELLER_DOMINANT = "SELLER_DOMINANT"
    NEUTRAL = "NEUTRAL"

# =====================================================
# DATA STRUCTURES
# =====================================================

@dataclass
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    oi: float = 0.0
    oi_change: float = 0.0

class KalmanFilter:
    def __init__(self, process_variance=1e-5, measurement_variance=1e-1):
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.posteri_estimate = 0.0
        self.posteri_error_estimate = 1.0

    def update(self, measurement):
        priori_estimate = self.posteri_estimate
        priori_error_estimate = self.posteri_error_estimate + self.process_variance
        blending_factor = priori_error_estimate / (priori_error_estimate + self.measurement_variance)
        self.posteri_estimate = priori_estimate + blending_factor * (measurement - priori_estimate)
        self.posteri_error_estimate = (1 - blending_factor) * priori_error_estimate
        return self.posteri_estimate

# =====================================================
# HELPER: Convert sqlite3.Row to dict
# =====================================================

def row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

def get_current_ist_minute() -> str:
    now_ist = datetime.now(IST)
    return now_ist.strftime("%Y-%m-%d %H:%M")

# =====================================================
# GLOBAL STATE
# =====================================================

candles_1m = {sym: deque(maxlen=200) for sym in ALL_TOKENS.values()}
candles_5m = {sym: deque(maxlen=100) for sym in ALL_TOKENS.values()}
kalman_filters = {sym: KalmanFilter() for sym in ALL_TOKENS.values()}
current_vix = 15.0

# =====================================================
# DATABASE CONNECTIONS
# =====================================================

def get_db_connections():
    candle_conn = sqlite3.connect(CANDLE_DB)
    candle_conn.row_factory = sqlite3.Row

    oi_conn = sqlite3.connect(OI_DB)
    oi_conn.row_factory = sqlite3.Row

    analytics_conn = sqlite3.connect(ANALYTICS_DB)

    return candle_conn, oi_conn, analytics_conn

def init_analytics_db(conn):
    cur = conn.cursor()

    # FIX 1 + FIX 3: Schema now includes bid_ask_bias and weighted_bias
    cur.execute("""
    CREATE TABLE IF NOT EXISTS minute_analytics (
        time_minute TEXT NOT NULL,
        instrument_token INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
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
        oi REAL,
        oi_change INTEGER,
        oi_category TEXT,
        ema_9_signal INTEGER DEFAULT 0,
        ema_21_signal INTEGER DEFAULT 0,
        ema_50_signal INTEGER DEFAULT 0,
        ema_200_signal INTEGER DEFAULT 0,
        macd_signal INTEGER DEFAULT 0,
        adx_trend_signal INTEGER DEFAULT 0,
        kalman_signal INTEGER DEFAULT 0,
        rsi_signal INTEGER DEFAULT 0,
        stoch_signal INTEGER DEFAULT 0,
        cci_signal INTEGER DEFAULT 0,
        mfi_signal INTEGER DEFAULT 0,
        roc_signal INTEGER DEFAULT 0,
        bb_signal INTEGER DEFAULT 0,
        atr_trend_signal INTEGER DEFAULT 0,
        vwap_signal INTEGER DEFAULT 0,
        volume_trend_signal INTEGER DEFAULT 0,
        obv_signal INTEGER DEFAULT 0,
        oi_signal INTEGER DEFAULT 0,
        depth_signal INTEGER DEFAULT 0,
        pattern_signal INTEGER DEFAULT 0,
        regime_signal INTEGER DEFAULT 0,
        ema_9_value REAL,
        ema_21_value REAL,
        ema_50_value REAL,
        ema_200_value REAL,
        macd_value REAL,
        macd_signal_value REAL,
        macd_histogram REAL,
        rsi_value REAL,
        stoch_k REAL,
        stoch_d REAL,
        cci_value REAL,
        mfi_value REAL,
        roc_value REAL,
        bb_upper REAL,
        bb_middle REAL,
        bb_lower REAL,
        atr_value REAL,
        vwap_value REAL,
        obv_value REAL,
        adx_value REAL,
        kalman_value REAL,
        bullish_count INTEGER,
        bearish_count INTEGER,
        neutral_count INTEGER,
        total_active INTEGER,
        bullish_percentage REAL,
        bearish_percentage REAL,
        market_regime TEXT,
        regime_confidence REAL,
        vix_value REAL,
        vix_state TEXT,
        detected_pattern TEXT,
        PRIMARY KEY (time_minute, instrument_token)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sector_analytics (
        time_minute TEXT NOT NULL,
        sector_name TEXT NOT NULL,
        buy_percentage REAL,
        sell_percentage REAL,
        signal TEXT,
        active_stocks INTEGER,
        PRIMARY KEY (time_minute, sector_name)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_direction (
        time_minute TEXT NOT NULL PRIMARY KEY,
        nifty_buy REAL,
        nifty_sell REAL,
        banknifty_buy REAL,
        banknifty_sell REAL,
        top10_buy REAL,
        top10_sell REAL,
        finnifty_buy REAL,
        finnifty_sell REAL,
        overall_buy REAL,
        overall_sell REAL,
        direction TEXT
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_analytics_time ON minute_analytics(time_minute)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_analytics_symbol ON minute_analytics(symbol)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sector_time ON sector_analytics(time_minute)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_market_time ON market_direction(time_minute)")

    conn.commit()
    cur.close()

# =====================================================
# TECHNICAL INDICATORS (21 INDICATORS)
# =====================================================

def calculate_ema(prices: List[float], period: int) -> float:
    if len(prices) < period:
        return 0.0
    try:
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    except:
        return 0.0

def calculate_rsi(prices: List[float], period=14) -> float:
    if len(prices) < period + 1:
        return 50.0
    try:
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    except:
        return 50.0

def calculate_macd(prices: List[float], fast=12, slow=26, signal=9) -> Tuple[float, float, float]:
    if len(prices) < slow:
        return 0.0, 0.0, 0.0
    try:
        ema_fast = calculate_ema(prices, fast)
        ema_slow = calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow

        macd_values = []
        for i in range(slow, len(prices)):
            ema_f = calculate_ema(prices[:i+1], fast)
            ema_s = calculate_ema(prices[:i+1], slow)
            macd_values.append(ema_f - ema_s)

        signal_line = calculate_ema(macd_values, signal) if len(macd_values) >= signal else 0.0
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram
    except:
        return 0.0, 0.0, 0.0

def calculate_stochastic(candles: List[Candle], period=14) -> Tuple[float, float]:
    if len(candles) < period:
        return 50.0, 50.0
    try:
        recent = candles[-period:]
        current_close = recent[-1].close
        lowest_low = min(c.low for c in recent)
        highest_high = max(c.high for c in recent)

        if highest_high - lowest_low == 0:
            return 50.0, 50.0

        k = 100 * (current_close - lowest_low) / (highest_high - lowest_low)
        d = k

        return k, d
    except:
        return 50.0, 50.0

def calculate_cci(candles: List[Candle], period=20) -> float:
    if len(candles) < period:
        return 0.0
    try:
        recent = candles[-period:]
        typical_prices = [(c.high + c.low + c.close) / 3 for c in recent]
        sma = sum(typical_prices) / len(typical_prices)
        mean_deviation = sum(abs(tp - sma) for tp in typical_prices) / len(typical_prices)

        if mean_deviation == 0:
            return 0.0

        current_tp = (recent[-1].high + recent[-1].low + recent[-1].close) / 3
        return (current_tp - sma) / (0.015 * mean_deviation)
    except:
        return 0.0

def calculate_mfi(candles: List[Candle], period=14) -> float:
    if len(candles) < period + 1:
        return 50.0
    try:
        positive_flow = 0
        negative_flow = 0

        for i in range(-period, 0):
            typical_price = (candles[i].high + candles[i].low + candles[i].close) / 3
            prev_typical = (candles[i-1].high + candles[i-1].low + candles[i-1].close) / 3
            money_flow = typical_price * candles[i].volume

            if typical_price > prev_typical:
                positive_flow += money_flow
            elif typical_price < prev_typical:
                negative_flow += money_flow

        if negative_flow == 0:
            return 100.0

        money_ratio = positive_flow / negative_flow
        return 100 - (100 / (1 + money_ratio))
    except:
        return 50.0

def calculate_bollinger_bands(prices: List[float], period=20, num_std=2) -> Tuple[float, float, float]:
    if len(prices) < period:
        return 0.0, 0.0, 0.0
    try:
        recent = prices[-period:]
        sma = sum(recent) / period
        variance = sum((p - sma) ** 2 for p in recent) / period
        std = variance ** 0.5

        return sma + (num_std * std), sma, sma - (num_std * std)
    except:
        return 0.0, 0.0, 0.0

def calculate_vwap(candles: List[Candle]) -> float:
    if not candles:
        return 0.0
    try:
        total_volume = sum(c.volume for c in candles)
        if total_volume == 0:
            return candles[-1].close

        return sum(((c.high + c.low + c.close) / 3) * c.volume for c in candles) / total_volume
    except:
        return 0.0

def calculate_obv(candles: List[Candle]) -> float:
    if len(candles) < 2:
        return 0.0
    try:
        obv = 0
        for i in range(1, len(candles)):
            if candles[i].close > candles[i-1].close:
                obv += candles[i].volume
            elif candles[i].close < candles[i-1].close:
                obv -= candles[i].volume
        return obv
    except:
        return 0.0

def calculate_roc(prices: List[float], period=12) -> float:
    if len(prices) < period + 1:
        return 0.0
    try:
        current = prices[-1]
        past = prices[-(period+1)]
        if past == 0:
            return 0.0
        return ((current - past) / past) * 100
    except:
        return 0.0

def calculate_atr(candles: List[Candle], period=14) -> float:
    if len(candles) < period + 1:
        return 0.0
    try:
        true_ranges = []
        for i in range(1, len(candles)):
            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - candles[i-1].close),
                abs(candles[i].low - candles[i-1].close)
            )
            true_ranges.append(tr)

        return sum(true_ranges[-period:]) / period if true_ranges else 0.0
    except:
        return 0.0

def calculate_adx(candles: List[Candle], period=14) -> float:
    if len(candles) < period + 1:
        return 0.0
    try:
        plus_dm_sum = 0
        minus_dm_sum = 0
        tr_sum = 0

        for i in range(1, min(period + 1, len(candles))):
            high_diff = candles[i].high - candles[i-1].high
            low_diff = candles[i-1].low - candles[i].low

            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0

            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - candles[i-1].close),
                abs(candles[i].low - candles[i-1].close)
            )

            plus_dm_sum += plus_dm
            minus_dm_sum += minus_dm
            tr_sum += tr

        if tr_sum == 0:
            return 0.0

        plus_di = 100 * (plus_dm_sum / tr_sum)
        minus_di = 100 * (minus_dm_sum / tr_sum)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0

        return dx
    except:
        return 0.0

def detect_pattern(candles: List[Candle]) -> Optional[str]:
    if len(candles) < 3:
        return None

    try:
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]

        if (c2.close < c2.open and c3.close > c3.open and
            c3.open < c2.close and c3.close > c2.open):
            return "BULLISH_ENGULFING"

        if (c2.close > c2.open and c3.close < c3.open and
            c3.open > c2.close and c3.close < c2.open):
            return "BEARISH_ENGULFING"

        if all(c.close > c.open for c in [c1, c2, c3]) and c3.close > c2.close > c1.close:
            return "THREE_WHITE_SOLDIERS"

        if all(c.close < c.open for c in [c1, c2, c3]) and c3.close < c2.close < c1.close:
            return "THREE_BLACK_CROWS"

    except:
        pass

    return None

def detect_regime(symbol: str) -> Tuple[MarketRegime, float]:
    try:
        candles_list = list(candles_5m.get(symbol, []))

        if len(candles_list) < 20:
            return MarketRegime.RANGING, 0.5

        recent_candles = candles_list[-50:] if len(candles_list) >= 50 else candles_list

        adx = calculate_adx(recent_candles, period=14)

        returns = []
        for i in range(1, len(recent_candles)):
            if recent_candles[i-1].close > 0:
                ret = (recent_candles[i].close - recent_candles[i-1].close) / recent_candles[i-1].close
                returns.append(abs(ret))

        current_vol = statistics.mean(returns) if returns else 0

        recent_close = recent_candles[-1].close
        sma_20 = sum(c.close for c in recent_candles[-20:]) / 20
        price_vs_sma = (recent_close - sma_20) / sma_20 if sma_20 > 0 else 0

        confidence = 0.5

        if current_vol > 0.02:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(current_vol * 50, 0.95)
        elif current_vol < 0.005:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = 0.7
        elif adx > ADX_THRESHOLD:
            if price_vs_sma > 0.01:
                regime = MarketRegime.TRENDING_UP
                confidence = min(adx / 50, 0.95)
            elif price_vs_sma < -0.01:
                regime = MarketRegime.TRENDING_DOWN
                confidence = min(adx / 50, 0.95)
            else:
                regime = MarketRegime.RANGING
                confidence = 1 - (adx / 50)
        else:
            regime = MarketRegime.RANGING
            confidence = 1 - (adx / 50)

        return regime, confidence
    except Exception as e:
        return MarketRegime.RANGING, 0.5

def analyze_vix() -> VixState:
    if current_vix < 12:
        return VixState.LOW
    elif current_vix < 15:
        return VixState.NORMAL
    elif current_vix < 18:
        return VixState.HIGH
    else:
        return VixState.EXTREME

def analyze_depth_bias(bid_ask_ratio: float, order_imbalance: int) -> DepthBias:
    if bid_ask_ratio >= BUY_THRESHOLD and order_imbalance >= ORDER_IMBALANCE_THRESHOLD:
        return DepthBias.BUYER_DOMINANT
    elif bid_ask_ratio <= SELL_THRESHOLD and order_imbalance <= -ORDER_IMBALANCE_THRESHOLD:
        return DepthBias.SELLER_DOMINANT
    else:
        return DepthBias.NEUTRAL

# =====================================================
# CALCULATE ALL INDICATORS
# =====================================================

def calculate_all_indicators(symbol: str, token: int, candle_data: dict, oi_category: str) -> dict:
    result = {
        'ema_9_signal': 0, 'ema_21_signal': 0, 'ema_50_signal': 0, 'ema_200_signal': 0,
        'macd_signal': 0, 'adx_trend_signal': 0, 'kalman_signal': 0,
        'rsi_signal': 0, 'stoch_signal': 0, 'cci_signal': 0, 'mfi_signal': 0,
        'roc_signal': 0, 'bb_signal': 0, 'atr_trend_signal': 0,
        'vwap_signal': 0, 'volume_trend_signal': 0, 'obv_signal': 0,
        'oi_signal': 0, 'depth_signal': 0, 'pattern_signal': 0, 'regime_signal': 0,
        'ema_9_value': 0.0, 'ema_21_value': 0.0, 'ema_50_value': 0.0, 'ema_200_value': 0.0,
        'macd_value': 0.0, 'macd_signal_value': 0.0, 'macd_histogram': 0.0,
        'rsi_value': 50.0, 'stoch_k': 50.0, 'stoch_d': 50.0,
        'cci_value': 0.0, 'mfi_value': 50.0, 'roc_value': 0.0,
        'bb_upper': 0.0, 'bb_middle': 0.0, 'bb_lower': 0.0,
        'atr_value': 0.0, 'vwap_value': 0.0, 'obv_value': 0.0,
        'adx_value': 0.0, 'kalman_value': 0.0,
        'bullish_count': 0, 'bearish_count': 0, 'neutral_count': 0,
        'total_active': 0, 'bullish_percentage': 0.0, 'bearish_percentage': 0.0,
        'market_regime': 'RANGING', 'regime_confidence': 0.5,
        'vix_value': current_vix, 'vix_state': analyze_vix().value,
        'detected_pattern': None
    }

    try:
        candles_list = list(candles_1m.get(symbol, []))
        if len(candles_list) < 20:
            return result

        prices = [c.close for c in candles_list]
        current_price = prices[-1]

        # 1-4. EMAs
        if len(prices) >= 200:
            for period, key in [(9, 'ema_9'), (21, 'ema_21'), (50, 'ema_50'), (200, 'ema_200')]:
                ema = calculate_ema(prices, period)
                result[f'{key}_value'] = ema
                if ema > 0:
                    result[f'{key}_signal'] = 1 if current_price > ema else -1

        # 5. MACD
        if len(prices) >= 35:
            macd_line, signal_line, histogram = calculate_macd(prices)
            result['macd_value'] = macd_line
            result['macd_signal_value'] = signal_line
            result['macd_histogram'] = histogram
            if histogram > 0 and macd_line > signal_line:
                result['macd_signal'] = 1
            elif histogram < 0 and macd_line < signal_line:
                result['macd_signal'] = -1

        # 6. ADX Trend
        candles_5m_list = list(candles_5m.get(symbol, []))
        if len(candles_5m_list) >= 20:
            adx = calculate_adx(candles_5m_list, 14)
            result['adx_value'] = adx
            if adx > ADX_THRESHOLD and len(prices) >= 20:
                sma_20 = sum(prices[-20:]) / 20
                result['adx_trend_signal'] = 1 if current_price > sma_20 else -1

        # 7. Kalman
        kalman = kalman_filters.get(symbol)
        if kalman:
            kalman_pred = kalman.update(current_price)
            result['kalman_value'] = kalman_pred
            result['kalman_signal'] = 1 if kalman_pred > current_price else -1

        # 8. RSI
        if len(prices) >= 15:
            rsi = calculate_rsi(prices, 14)
            result['rsi_value'] = rsi
            if rsi < RSI_OVERSOLD:
                result['rsi_signal'] = 1
            elif rsi > RSI_OVERBOUGHT:
                result['rsi_signal'] = -1

        # 9-17. Other indicators
        if len(candles_list) >= 15:
            k, d = calculate_stochastic(candles_list, 14)
            result['stoch_k'] = k
            result['stoch_d'] = d
            if k < 20 and k > d:
                result['stoch_signal'] = 1
            elif k > 80 and k < d:
                result['stoch_signal'] = -1

        if len(candles_list) >= 20:
            cci = calculate_cci(candles_list, 20)
            result['cci_value'] = cci
            if cci < -100:
                result['cci_signal'] = 1
            elif cci > 100:
                result['cci_signal'] = -1

        if len(candles_list) >= 15:
            mfi = calculate_mfi(candles_list, 14)
            result['mfi_value'] = mfi
            if mfi < 20:
                result['mfi_signal'] = 1
            elif mfi > 80:
                result['mfi_signal'] = -1

        if len(prices) >= 13:
            roc = calculate_roc(prices, 12)
            result['roc_value'] = roc
            result['roc_signal'] = 1 if roc > 0 else -1

        if len(prices) >= 20:
            upper, middle, lower = calculate_bollinger_bands(prices, 20)
            result['bb_upper'] = upper
            result['bb_middle'] = middle
            result['bb_lower'] = lower
            if current_price < lower:
                result['bb_signal'] = 1
            elif current_price > upper:
                result['bb_signal'] = -1

        if len(candles_5m_list) >= 15:
            atr = calculate_atr(candles_5m_list, 14)
            result['atr_value'] = atr
            atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
            if atr_pct > 1.5 and len(prices) >= 20:
                sma = sum(prices[-20:]) / 20
                result['atr_trend_signal'] = 1 if current_price > sma else -1

        if len(candles_list) >= 20:
            vwap = calculate_vwap(candles_list[-20:])
            result['vwap_value'] = vwap
            if vwap > 0:
                result['vwap_signal'] = 1 if current_price > vwap else -1

        if len(candles_list) >= 20:
            recent_vol = sum(c.volume for c in candles_list[-5:]) / 5
            avg_vol = sum(c.volume for c in candles_list[-20:]) / 20
            if recent_vol > avg_vol * 1.5 and len(prices) >= 5:
                price_change = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] > 0 else 0
                result['volume_trend_signal'] = 1 if price_change > 0 else -1

        if len(candles_list) >= 20:
            obv = calculate_obv(candles_list[-20:])
            result['obv_value'] = obv
            result['obv_signal'] = 1 if obv > 0 else -1

        # 18. OI Signal
        if oi_category in ["LB", "SC"]:
            result['oi_signal'] = 1
        elif oi_category in ["SB", "LU"]:
            result['oi_signal'] = -1

        # 19. Depth Signal
        bid_ask_ratio = candle_data.get('bid_ask_ratio', 1.0)
        order_imbalance = candle_data.get('order_imbalance', 0)
        depth_bias = analyze_depth_bias(bid_ask_ratio, order_imbalance)

        if depth_bias == DepthBias.BUYER_DOMINANT:
            result['depth_signal'] = 1
        elif depth_bias == DepthBias.SELLER_DOMINANT:
            result['depth_signal'] = -1

        # 20. Pattern Signal
        pattern = detect_pattern(candles_list[-3:]) if len(candles_list) >= 3 else None
        if pattern:
            result['detected_pattern'] = pattern
            if "BULLISH" in pattern or "WHITE" in pattern:
                result['pattern_signal'] = 1
            elif "BEARISH" in pattern or "BLACK" in pattern:
                result['pattern_signal'] = -1

        # 21. Regime Signal
        regime, confidence = detect_regime(symbol)
        result['market_regime'] = regime.value
        result['regime_confidence'] = confidence

        if regime == MarketRegime.TRENDING_UP:
            result['regime_signal'] = 1
        elif regime == MarketRegime.TRENDING_DOWN:
            result['regime_signal'] = -1

        # Calculate aggregated metrics using constant SIGNAL_KEYS
        signals = [result[f'{k}_signal'] for k in SIGNAL_KEYS]

        result['bullish_count'] = sum(1 for s in signals if s == 1)
        result['bearish_count'] = sum(1 for s in signals if s == -1)
        result['neutral_count'] = sum(1 for s in signals if s == 0)
        result['total_active'] = result['bullish_count'] + result['bearish_count']

        if result['total_active'] > 0:
            result['bullish_percentage'] = (result['bullish_count'] / result['total_active']) * 100
            result['bearish_percentage'] = (result['bearish_count'] / result['total_active']) * 100

    except Exception as e:
        print(f"[INDICATOR ERR] {symbol}: {e}")

    return result

# =====================================================
# SECTOR & MARKET ANALYSIS
# =====================================================

def calculate_sector_analysis(time_str: str, analytics_conn) -> None:
    try:
        cur = analytics_conn.cursor()

        for sector_name, token_list in SECTORS.items():
            buy_total = 0
            sell_total = 0
            active_count = 0

            for token in token_list:
                cur.execute("""
                    SELECT bullish_percentage, bearish_percentage, total_active
                    FROM minute_analytics
                    WHERE instrument_token = ? AND time_minute = ?
                """, (token, time_str))

                row = cur.fetchone()
                if row and row[2] > 0:
                    buy_total += row[0]
                    sell_total += row[1]
                    active_count += 1

            if active_count > 0:
                avg_buy = buy_total / active_count
                avg_sell = sell_total / active_count

                signal = "BUY" if avg_buy > 60 else "SELL" if avg_sell > 60 else "NEUTRAL"

                cur.execute("""
                    INSERT OR REPLACE INTO sector_analytics
                    (time_minute, sector_name, buy_percentage, sell_percentage, signal, active_stocks)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (time_str, sector_name, avg_buy, avg_sell, signal, active_count))

        analytics_conn.commit()
        cur.close()
    except Exception as e:
        print(f"[SECTOR ERR] {time_str}: {e}")

def calculate_market_direction(time_str: str, analytics_conn) -> None:
    try:
        cur = analytics_conn.cursor()

        indices_data = {}
        for token, symbol in INDEX_TOKENS.items():
            cur.execute("""
                SELECT bullish_percentage, bearish_percentage
                FROM minute_analytics
                WHERE instrument_token = ? AND time_minute = ?
            """, (token, time_str))

            row = cur.fetchone()
            if row:
                indices_data[symbol] = {'buy': row[0], 'sell': row[1]}

        top10_buy = 0
        top10_sell = 0
        top10_count = 0

        for token in STOCK_TOKENS.keys():
            cur.execute("""
                SELECT bullish_percentage, bearish_percentage, total_active
                FROM minute_analytics
                WHERE instrument_token = ? AND time_minute = ?
            """, (token, time_str))

            row = cur.fetchone()
            if row and row[2] > 0:
                top10_buy += row[0]
                top10_sell += row[1]
                top10_count += 1

        if top10_count > 0:
            top10_buy /= top10_count
            top10_sell /= top10_count

        nifty_buy = indices_data.get('NIFTY', {}).get('buy', 0)
        nifty_sell = indices_data.get('NIFTY', {}).get('sell', 0)
        bnf_buy = indices_data.get('BANKNIFTY', {}).get('buy', 0)
        bnf_sell = indices_data.get('BANKNIFTY', {}).get('sell', 0)
        finn_buy = indices_data.get('FINNIFTY', {}).get('buy', 0)
        finn_sell = indices_data.get('FINNIFTY', {}).get('sell', 0)

        overall_buy = (nifty_buy * 0.3 + bnf_buy * 0.4 + top10_buy * 0.2 + finn_buy * 0.1)
        overall_sell = (nifty_sell * 0.3 + bnf_sell * 0.4 + top10_sell * 0.2 + finn_sell * 0.1)

        direction = "STRONG_BUY" if overall_buy > 65 else "BUY" if overall_buy > 55 else \
                   "STRONG_SELL" if overall_sell > 65 else "SELL" if overall_sell > 55 else "NEUTRAL"

        cur.execute("""
            INSERT OR REPLACE INTO market_direction
            (time_minute, nifty_buy, nifty_sell, banknifty_buy, banknifty_sell,
             top10_buy, top10_sell, finnifty_buy, finnifty_sell, overall_buy, overall_sell, direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (time_str, nifty_buy, nifty_sell, bnf_buy, bnf_sell,
              top10_buy, top10_sell, finn_buy, finn_sell, overall_buy, overall_sell, direction))

        analytics_conn.commit()
        cur.close()
    except Exception as e:
        print(f"[MARKET DIR ERR] {time_str}: {e}")

# =====================================================
# MAIN PROCESSING
# =====================================================

def process_latest_candles():
    candle_conn, oi_conn, analytics_conn = get_db_connections()

    try:
        candle_cur = candle_conn.cursor()
        oi_cur = oi_conn.cursor()
        analytics_cur = analytics_conn.cursor()

        current_minute = get_current_ist_minute()

        analytics_cur.execute("""
            SELECT COALESCE(MAX(time_minute), '2000-01-01 00:00') as last_time
            FROM minute_analytics
        """)
        last_time = analytics_cur.fetchone()[0]

        candle_cur.execute("""
            SELECT DISTINCT time_minute
            FROM minute_candles
            WHERE time_minute > ?
              AND time_minute < ?
            ORDER BY time_minute ASC
        """, (last_time, current_minute))

        time_rows = candle_cur.fetchall()

        if not time_rows:
            return 0

        processed_count = 0

        for time_row in time_rows:
            time_str = time_row[0]

            candle_cur.execute("""
                SELECT 
                    instrument_token,
                    time_minute,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    total_bid_qty,
                    total_ask_qty,
                    bid_ask_ratio,
                    order_imbalance,
                    bid_ask_bias,
                    weighted_bid_qty,
                    weighted_ask_qty,
                    weighted_bid_ask_ratio,
                    weighted_order_imbalance,
                    weighted_bias
                FROM minute_candles
                WHERE time_minute = ?
            """, (time_str,))

            candles_at_time = candle_cur.fetchall()

            for row in candles_at_time:
                row_dict = row_to_dict(row)
                token = row_dict["instrument_token"]

                if token == VIX_TOKEN:
                    continue

                if token not in PROCESSING_TOKENS:
                    continue

                symbol = PROCESSING_TOKENS.get(token, f"UNKNOWN_{token}")

                candle_data = {
                    'time_minute': time_str,
                    'open': row_dict["open"],
                    'high': row_dict["high"],
                    'low': row_dict["low"],
                    'close': row_dict["close"],
                    'volume': row_dict["volume"] or 0,
                    'total_bid_qty': row_dict["total_bid_qty"] or 0,
                    'total_ask_qty': row_dict["total_ask_qty"] or 0,
                    'bid_ask_ratio': row_dict["bid_ask_ratio"] or 1.0,
                    'order_imbalance': row_dict["order_imbalance"] or 0,
                    'bid_ask_bias': row_dict["bid_ask_bias"],
                    'weighted_bid_qty': row_dict["weighted_bid_qty"] or 0,
                    'weighted_ask_qty': row_dict["weighted_ask_qty"] or 0,
                    'weighted_bid_ask_ratio': row_dict["weighted_bid_ask_ratio"] or 1.0,
                    'weighted_order_imbalance': row_dict["weighted_order_imbalance"] or 0,
                    'weighted_bias': row_dict["weighted_bias"]
                }

                candle = Candle(
                    timestamp=time_str,
                    open=row_dict["open"],
                    high=row_dict["high"],
                    low=row_dict["low"],
                    close=row_dict["close"],
                    volume=row_dict["volume"] or 0,
                    oi=0,
                    oi_change=0
                )

                candles_1m[symbol].append(candle)

                if len(candles_1m[symbol]) >= 5:
                    candles_list = list(candles_1m[symbol])
                    last_5 = candles_list[-5:]
                    candle_5m = Candle(
                        timestamp=time_str,
                        open=last_5[0].open,
                        high=max(c.high for c in last_5),
                        low=min(c.low for c in last_5),
                        close=last_5[-1].close,
                        volume=sum(c.volume for c in last_5),
                        oi=0,
                        oi_change=0
                    )
                    if not candles_5m[symbol] or candles_5m[symbol][-1].timestamp != time_str:
                        candles_5m[symbol].append(candle_5m)

                oi_category = "NA"
                oi_change = 0

                if token in FUTURE_TOKENS:
                    oi_cur.execute("""
                        SELECT oi_category, oi_change 
                        FROM futures_oi_category_1m
                        WHERE instrument_token = ? AND time_minute = ?
                    """, (token, time_str))
                    oi_row = oi_cur.fetchone()
                    if oi_row:
                        oi_dict = row_to_dict(oi_row)
                        oi_category = oi_dict.get("oi_category", "NA")
                        oi_change = oi_dict.get("oi_change", 0) or 0

                indicators = calculate_all_indicators(symbol, token, candle_data, oi_category)

                # FIX 1 + FIX 2 + FIX 3: INSERT with bid_ask_bias, weighted_bias, and oi = oi_change
                analytics_cur.execute("""
                    INSERT OR REPLACE INTO minute_analytics (
                        time_minute, instrument_token, symbol,
                        open, high, low, close, volume,
                        total_bid_qty, total_ask_qty, bid_ask_ratio, order_imbalance, bid_ask_bias,
                        weighted_bid_qty, weighted_ask_qty, weighted_bid_ask_ratio, weighted_order_imbalance, weighted_bias,
                        oi, oi_change, oi_category,
                        ema_9_signal, ema_21_signal, ema_50_signal, ema_200_signal,
                        macd_signal, adx_trend_signal, kalman_signal,
                        rsi_signal, stoch_signal, cci_signal, mfi_signal,
                        roc_signal, bb_signal, atr_trend_signal,
                        vwap_signal, volume_trend_signal, obv_signal,
                        oi_signal, depth_signal, pattern_signal, regime_signal,
                        ema_9_value, ema_21_value, ema_50_value, ema_200_value,
                        macd_value, macd_signal_value, macd_histogram,
                        rsi_value, stoch_k, stoch_d,
                        cci_value, mfi_value, roc_value,
                        bb_upper, bb_middle, bb_lower,
                        atr_value, vwap_value, obv_value, adx_value, kalman_value,
                        bullish_count, bearish_count, neutral_count,
                        total_active, bullish_percentage, bearish_percentage,
                        market_regime, regime_confidence, vix_value, vix_state, detected_pattern
                    ) VALUES (
                        ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                """, (
                    time_str, token, symbol,
                    candle_data['open'], candle_data['high'], candle_data['low'], 
                    candle_data['close'], candle_data['volume'],
                    candle_data['total_bid_qty'], candle_data['total_ask_qty'],
                    candle_data['bid_ask_ratio'], candle_data['order_imbalance'],
                    candle_data['bid_ask_bias'],
                    candle_data['weighted_bid_qty'], candle_data['weighted_ask_qty'],
                    candle_data['weighted_bid_ask_ratio'], candle_data['weighted_order_imbalance'],
                    candle_data['weighted_bias'],
                    oi_change, oi_change, oi_category,  # FIX 2: oi = oi_change as fallback
                    indicators['ema_9_signal'], indicators['ema_21_signal'],
                    indicators['ema_50_signal'], indicators['ema_200_signal'],
                    indicators['macd_signal'], indicators['adx_trend_signal'], indicators['kalman_signal'],
                    indicators['rsi_signal'], indicators['stoch_signal'], indicators['cci_signal'],
                    indicators['mfi_signal'], indicators['roc_signal'], indicators['bb_signal'],
                    indicators['atr_trend_signal'], indicators['vwap_signal'],
                    indicators['volume_trend_signal'], indicators['obv_signal'],
                    indicators['oi_signal'], indicators['depth_signal'],
                    indicators['pattern_signal'], indicators['regime_signal'],
                    indicators['ema_9_value'], indicators['ema_21_value'],
                    indicators['ema_50_value'], indicators['ema_200_value'],
                    indicators['macd_value'], indicators['macd_signal_value'], indicators['macd_histogram'],
                    indicators['rsi_value'], indicators['stoch_k'], indicators['stoch_d'],
                    indicators['cci_value'], indicators['mfi_value'], indicators['roc_value'],
                    indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'],
                    indicators['atr_value'], indicators['vwap_value'], indicators['obv_value'],
                    indicators['adx_value'], indicators['kalman_value'],
                    indicators['bullish_count'], indicators['bearish_count'], indicators['neutral_count'],
                    indicators['total_active'], indicators['bullish_percentage'], indicators['bearish_percentage'],
                    indicators['market_regime'], indicators['regime_confidence'],
                    indicators['vix_value'], indicators['vix_state'], indicators['detected_pattern']
                ))

                processed_count += 1

            analytics_conn.commit()

            calculate_sector_analysis(time_str, analytics_conn)
            calculate_market_direction(time_str, analytics_conn)

        candle_cur.close()
        oi_cur.close()
        analytics_cur.close()

        return processed_count

    except Exception as e:
        print(f"[PROCESS ERR] {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        candle_conn.close()
        oi_conn.close()
        analytics_conn.close()

# =====================================================
# MAIN LOOP
# =====================================================

def main():
    print("=" * 80)
    print("🚀 Comprehensive Analytics Engine Started (PRODUCTION)")
    print("=" * 80)
    print(f"📊 Calculating 21 indicators for {len(PROCESSING_TOKENS)} symbols")
    print(f"📈 Indices: {len(INDEX_TOKENS)}")
    print(f"🏦 Stocks: {len(STOCK_TOKENS)}")
    print(f"🏛️  NBFC: {len(NBFC_TOKENS)}")
    print("=" * 80)

    _, _, analytics_conn = get_db_connections()
    init_analytics_db(analytics_conn)
    analytics_conn.close()
    print("✅ Database initialized\n")

    print("🔄 Running continuously...\n")

    consecutive_empty = 0
    error_count = 0
    max_errors = 10

    while True:
        try:
            import time as time_module
            start = time_module.time()

            processed = process_latest_candles()

            if processed > 0:
                elapsed = time_module.time() - start
                timestamp = datetime.now(IST).strftime("%H:%M:%S")
                print(f"[{timestamp}] ✅ Processed {processed} rows ({elapsed:.1f}s)")
                consecutive_empty = 0
                error_count = 0
            else:
                consecutive_empty += 1
                if consecutive_empty % 10 == 0:
                    timestamp = datetime.now(IST).strftime("%H:%M:%S")
                    print(f"[{timestamp}] ⏳ Waiting for new candles... ({consecutive_empty} checks)")

            time.sleep(60)

        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down gracefully...")
            break
        except Exception as e:
            error_count += 1
            timestamp = datetime.now(IST).strftime("%H:%M:%S")
            print(f"[{timestamp}] ❌ Error in main loop: {e}")

            if error_count >= max_errors:
                print(f"❌ Too many consecutive errors ({max_errors}). Exiting...")
                break

            print(f"⏸️  Pausing for 5 seconds before retry... (Error {error_count}/{max_errors})")
            time.sleep(5)

    print("✅ Analytics engine stopped")
    print("👋 Goodbye!")

if __name__ == "__main__":
    main()
