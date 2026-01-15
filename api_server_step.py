#!/usr/bin/env python3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from typing import List, Optional
from datetime import datetime, timedelta

# =====================================================
# CONFIG
# =====================================================

CANDLE_DB = "minute_candles.db"
OI_DB = "oi_analysis.db"
ANALYTICS_DB = "market_analytics.db"
ALERT_DB = "alerts_pro.db"

# Futures only (for OI category mapping)
FUTURE_TOKENS = {
    13568258: "BANKNIFTY_FUT",
    256265: "NIFTY_FUT"
}

app = FastAPI(title="Professional Market Data API", version="4.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# DB HELPERS
# =====================================================

def get_candle_db():
    conn = sqlite3.connect(CANDLE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_oi_db():
    conn = sqlite3.connect(OI_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_analytics_db():
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_alert_db():
    conn = sqlite3.connect(ALERT_DB)
    conn.row_factory = sqlite3.Row
    return conn

# =====================================================
# ENDPOINT 1: LATEST MARKET SNAPSHOT
# =====================================================

@app.get("/market/latest")
def market_latest():
    """Get latest candle data for all symbols"""
    candle_conn = get_candle_db()
    oi_conn = get_oi_db()

    candle_cur = candle_conn.cursor()
    oi_cur = oi_conn.cursor()

    # Get latest candle for each instrument
    candle_cur.execute("""
        SELECT c.*
        FROM candles_1m c
        INNER JOIN (
            SELECT instrument_token, MAX(time_minute) AS max_time
            FROM candles_1m
            GROUP BY instrument_token
        ) latest
        ON c.instrument_token = latest.instrument_token
        AND c.time_minute = latest.max_time
        ORDER BY c.symbol
    """)

    candles = candle_cur.fetchall()
    result = []

    for c in candles:
        token = c["instrument_token"]
        oi_change = 0
        oi_category = "NA"

        # Only FUTURES get OI category
        if token in FUTURE_TOKENS:
            oi_cur.execute("""
                SELECT oi_change, oi_category
                FROM oi_category_1m
                WHERE instrument_token = ?
                  AND time_minute = ?
            """, (token, c["time_minute"]))

            oi = oi_cur.fetchone()
            if oi:
                oi_change = oi["oi_change"]
                oi_category = oi["oi_category"]

        result.append({
            "symbol": c["symbol"],
            "time": c["time_minute"][:16],
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"],
            "volume": c["volume"],
            "bid_ask_ratio": round(c["bid_ask_ratio"], 2),
            "order_imbalance": c["order_imbalance"],
            "oi_change": oi_change,
            "oi_category": oi_category
        })

    candle_conn.close()
    oi_conn.close()

    return result

# =====================================================
# ENDPOINT 2: ANALYTICS DATA
# =====================================================

@app.get("/analytics/latest")
def analytics_latest():
    """Get latest analytics for all symbols"""
    conn = get_analytics_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT a.*
        FROM minute_analytics a
        INNER JOIN (
            SELECT instrument_token, MAX(time_minute) AS max_time
            FROM minute_analytics
            GROUP BY instrument_token
        ) latest
        ON a.instrument_token = latest.instrument_token
        AND a.time_minute = latest.max_time
        ORDER BY a.symbol
    """)
    
    rows = cur.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        data = dict(row)
        data['time'] = data['time_minute'][:16]
        result.append(data)
    
    return result

@app.get("/analytics/symbol/{symbol}")
def analytics_by_symbol(symbol: str, limit: int = 50):
    """Get analytics history for a specific symbol"""
    conn = get_analytics_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM minute_analytics
        WHERE symbol = ?
        ORDER BY time_minute DESC
        LIMIT ?
    """, (symbol, limit))
    
    rows = cur.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        data = dict(row)
        data['time'] = data['time_minute'][:16]
        result.append(data)
    
    return result[::-1]  # Return chronological order

# =====================================================
# ENDPOINT 3: SECTOR ANALYSIS
# =====================================================

@app.get("/analytics/sectors")
def get_sectors():
    """Get latest sector analysis"""
    conn = get_analytics_db()
    cur = conn.cursor()
    
    # Get latest time
    cur.execute("SELECT MAX(time_minute) as latest FROM sector_analytics")
    latest = cur.fetchone()
    
    if not latest or not latest['latest']:
        conn.close()
        return []
    
    cur.execute("""
        SELECT * FROM sector_analytics
        WHERE time_minute = ?
    """, (latest['latest'],))
    
    rows = cur.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# =====================================================
# ENDPOINT 4: MARKET DIRECTION
# =====================================================

@app.get("/analytics/market-direction")
def get_market_direction():
    """Get latest market direction"""
    conn = get_analytics_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM market_direction
        ORDER BY time_minute DESC
        LIMIT 1
    """)
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return {}

# =====================================================
# ENDPOINT 5: ALERTS
# =====================================================

@app.get("/alerts/latest")
def get_latest_alerts(limit: int = 20):
    """Get latest alerts"""
    conn = get_alert_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM alerts_final
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    
    rows = cur.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.get("/alerts/symbol/{symbol}")
def get_alerts_by_symbol(symbol: str, limit: int = 10):
    """Get alerts for specific symbol"""
    conn = get_alert_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM alerts_final
        WHERE symbol = ?
        ORDER BY id DESC
        LIMIT ?
    """, (symbol, limit))
    
    rows = cur.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.get("/alerts/high-confidence")
def get_high_confidence_alerts(min_confidence: int = 70, limit: int = 20):
    """Get high confidence alerts"""
    conn = get_alert_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM alerts_final
        WHERE confidence >= ?
        ORDER BY id DESC
        LIMIT ?
    """, (min_confidence, limit))
    
    rows = cur.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# =====================================================
# ENDPOINT 6: OI ANALYSIS
# =====================================================

@app.get("/oi/latest")
def get_latest_oi():
    """Get latest OI categories"""
    conn = get_oi_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT o.*
        FROM oi_category_1m o
        INNER JOIN (
            SELECT instrument_token, MAX(time_minute) AS max_time
            FROM oi_category_1m
            GROUP BY instrument_token
        ) latest
        ON o.instrument_token = latest.instrument_token
        AND o.time_minute = latest.max_time
        ORDER BY o.symbol
    """)
    
    rows = cur.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        data = dict(row)
        data['time'] = data['time_minute'][:16]
        result.append(data)
    
    return result

@app.get("/oi/history/{symbol}")
def get_oi_history(symbol: str, hours: int = 1):
    """Get OI history for symbol"""
    conn = get_oi_db()
    cur = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:00")
    
    cur.execute("""
        SELECT * FROM oi_category_1m
        WHERE symbol = ? AND time_minute >= ?
        ORDER BY time_minute ASC
    """, (symbol, cutoff))
    
    rows = cur.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# =====================================================
# ENDPOINT 7: DASHBOARD SUMMARY
# =====================================================

@app.get("/dashboard/summary")
def get_dashboard_summary():
    """Get complete dashboard summary"""
    
    # Get latest market data
    market_data = market_latest()
    
    # Get analytics
    analytics = analytics_latest()
    
    # Get sectors
    sectors = get_sectors()
    
    # Get market direction
    market_direction = get_market_direction()
    
    # Get latest alerts
    alerts = get_latest_alerts(limit=10)
    
    # Get OI data
    oi_data = get_latest_oi()
    
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_data": market_data,
        "analytics": analytics,
        "sectors": sectors,
        "market_direction": market_direction,
        "recent_alerts": alerts,
        "oi_data": oi_data
    }

# =====================================================
# ENDPOINT 8: TIME SERIES DATA
# =====================================================

@app.get("/timeseries/candles/{symbol}")
def get_candle_timeseries(symbol: str, hours: int = 1):
    """Get candle time series for charting"""
    conn = get_candle_db()
    cur = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:00")
    
    cur.execute("""
        SELECT time_minute, open, high, low, close, volume
        FROM candles_1m
        WHERE symbol = ? AND time_minute >= ?
        ORDER BY time_minute ASC
    """, (symbol, cutoff))
    
    rows = cur.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.get("/timeseries/indicators/{symbol}")
def get_indicator_timeseries(symbol: str, hours: int = 1):
    """Get indicator time series for charting"""
    conn = get_analytics_db()
    cur = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:00")
    
    cur.execute("""
        SELECT time_minute, 
               ema_9_value, ema_21_value, ema_50_value, ema_200_value,
               rsi_value, macd_value, macd_signal_value,
               bb_upper, bb_middle, bb_lower,
               bullish_percentage, bearish_percentage
        FROM minute_analytics
        WHERE symbol = ? AND time_minute >= ?
        ORDER BY time_minute ASC
    """, (symbol, cutoff))
    
    rows = cur.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# =====================================================
# HEALTH CHECK
# =====================================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test all DB connections
        candle_conn = get_candle_db()
        candle_conn.close()
        
        oi_conn = get_oi_db()
        oi_conn.close()
        
        analytics_conn = get_analytics_db()
        analytics_conn.close()
        
        alert_conn = get_alert_db()
        alert_conn.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "databases": {
                "candles": "connected",
                "oi": "connected",
                "analytics": "connected",
                "alerts": "connected"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Professional Market Data API Server")
    print("📊 Serving comprehensive analytics and alerts")
    print("🌐 Starting on http://localhost:8000")
    print("📖 Docs available at http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
