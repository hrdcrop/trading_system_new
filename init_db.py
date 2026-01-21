#!/usr/bin/env python3
import sqlite3
from datetime import datetime

print("🚀 Initializing Trading System Databases\n")

# ============= MARKET_DATA.DB =============
conn = sqlite3.connect('market_data.db')
c = conn.cursor()

print("📊 Creating market_data.db schema...")

# Candles table
c.execute('''
    CREATE TABLE IF NOT EXISTS candles_1m (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        oi INTEGER,
        UNIQUE(symbol, timestamp)
    )
''')
c.execute('CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles_1m(symbol, timestamp)')

# OI Categories
c.execute('''
    CREATE TABLE IF NOT EXISTS oi_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        total_oi INTEGER,
        call_oi INTEGER,
        put_oi INTEGER,
        pcr REAL,
        category TEXT,
        atm_strike INTEGER,
        UNIQUE(symbol, timestamp)
    )
''')
c.execute('CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON oi_categories(symbol, timestamp)')

# Comprehensive Analytics
c.execute('''
    CREATE TABLE IF NOT EXISTS comprehensive_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        regime TEXT,
        trend_strength REAL,
        momentum REAL,
        volatility REAL,
        ema_20 REAL,
        ema_50 REAL,
        ema_200 REAL,
        rsi REAL,
        macd REAL,
        signal REAL,
        vwap REAL,
        bb_upper REAL,
        bb_lower REAL,
        stoch_k REAL,
        stoch_d REAL,
        adx REAL,
        confidence REAL,
        signal_strength TEXT,
        UNIQUE(symbol, timestamp)
    )
''')
c.execute('CREATE INDEX IF NOT EXISTS idx_analytics_symbol_time ON comprehensive_analytics(symbol, timestamp)')

conn.commit()
print(f"✅ Created {len(c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall())} tables")
conn.close()

# ============= ALERTS_PRO.DB =============
conn = sqlite3.connect('alerts_pro.db')
c = conn.cursor()

print("🚨 Fixing alerts_pro.db schema...")

# Rename alerts_final to alerts
c.execute('DROP TABLE IF EXISTS alerts')
c.execute('''
    CREATE TABLE alerts AS 
    SELECT 
        id,
        time as timestamp,
        symbol,
        recommended_action as alert_type,
        recommended_action as signal,
        confidence,
        NULL as price,
        regime,
        metadata as details,
        telegram_sent,
        time as created_at
    FROM alerts_final
''')

c.execute('CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp)')
c.execute('CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol)')

# Keep alert_state as is
print("✅ Migrated alerts_final → alerts")

conn.commit()
conn.close()

print("\n✅ Database initialization complete!")
print("="*60)
