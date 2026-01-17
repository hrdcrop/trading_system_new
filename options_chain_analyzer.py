#!/usr/bin/env python3
"""
OPTIONS CHAIN ANALYZER
Real-time Options Chain Analysis with Greeks, PCR, Max Pain

Features:
- Live Option Chain fetching
- Greeks calculation (Delta, Gamma, Theta, Vega)
- Put-Call Ratio (PCR) analysis
- Max Pain calculation
- OI Build-up detection
- Strike-wise analysis
"""

import sqlite3
import time
import requests
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math

# =====================================================
# CONFIG
# =====================================================

API_KEY = open("api_key.txt").read().strip()
ACCESS_TOKEN = open("access_token.txt").read().strip()

OPTIONS_DB = "options_chain.db"
ANALYTICS_DB = "market_analytics.db"

# Kite Connect headers
KITE_HEADERS = {
    "X-Kite-Version": "3",
    "Authorization": f"token {API_KEY}:{ACCESS_TOKEN}"
}

# Index symbols for options
INDICES = {
    "NIFTY": {"token": 256265, "lot_size": 50, "strike_gap": 50},
    "BANKNIFTY": {"token": 260105, "lot_size": 15, "strike_gap": 100},
    "FINNIFTY": {"token": 257801, "lot_size": 40, "strike_gap": 50}
}

# Risk-free rate for Greeks calculation
RISK_FREE_RATE = 0.07  # 7% annual

# =====================================================
# DATA STRUCTURES
# =====================================================

@dataclass
class OptionData:
    symbol: str
    strike: float
    expiry: str
    option_type: str  # CE or PE
    ltp: float
    oi: int
    oi_change: int
    volume: int
    bid: float
    ask: float
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float

@dataclass
class OptionsChainAnalysis:
    timestamp: str
    symbol: str
    spot_price: float
    atm_strike: float
    pcr_oi: float
    pcr_volume: float
    max_pain: float
    call_oi_total: int
    put_oi_total: int
    call_vol_total: int
    put_vol_total: int
    bullish_strikes: List[float]
    bearish_strikes: List[float]
    resistance_levels: List[float]
    support_levels: List[float]

# =====================================================
# DATABASE SETUP
# =====================================================

def init_options_db():
    """Initialize options chain database"""
    conn = sqlite3.connect(OPTIONS_DB)
    cur = conn.cursor()
    
    # Options chain snapshot table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS options_chain (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL,
        strike REAL NOT NULL,
        expiry TEXT NOT NULL,
        option_type TEXT NOT NULL,
        
        ltp REAL,
        oi INTEGER,
        oi_change INTEGER,
        volume INTEGER,
        bid REAL,
        ask REAL,
        
        iv REAL,
        delta REAL,
        gamma REAL,
        theta REAL,
        vega REAL
    )
    """)
    
    # Options analysis table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS options_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL,
        spot_price REAL,
        atm_strike REAL,
        
        pcr_oi REAL,
        pcr_volume REAL,
        max_pain REAL,
        
        call_oi_total INTEGER,
        put_oi_total INTEGER,
        call_vol_total INTEGER,
        put_vol_total INTEGER,
        
        bullish_strikes TEXT,
        bearish_strikes TEXT,
        resistance_levels TEXT,
        support_levels TEXT,
        
        analysis_text TEXT
    )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_options_time ON options_chain(timestamp)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_options_symbol ON options_chain(symbol)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_analysis_time ON options_analysis(timestamp)")
    
    conn.commit()
    return conn

# =====================================================
# GREEKS CALCULATION (Black-Scholes)
# =====================================================

def calculate_greeks(spot: float, strike: float, time_to_expiry: float, 
                     volatility: float, option_type: str) -> Tuple[float, float, float, float]:
    """
    Calculate option Greeks using Black-Scholes model
    Returns: (delta, gamma, theta, vega)
    """
    try:
        if time_to_expiry <= 0:
            return (0.0, 0.0, 0.0, 0.0)
        
        # Convert IV from percentage to decimal
        sigma = volatility / 100.0
        
        # Black-Scholes parameters
        d1 = (math.log(spot / strike) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * time_to_expiry) / (sigma * math.sqrt(time_to_expiry))
        d2 = d1 - sigma * math.sqrt(time_to_expiry)
        
        # Standard normal CDF approximation
        def norm_cdf(x):
            return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
        
        # Standard normal PDF
        def norm_pdf(x):
            return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)
        
        # Delta
        if option_type == "CE":
            delta = norm_cdf(d1)
        else:  # PE
            delta = norm_cdf(d1) - 1
        
        # Gamma (same for both CE and PE)
        gamma = norm_pdf(d1) / (spot * sigma * math.sqrt(time_to_expiry))
        
        # Theta (daily)
        if option_type == "CE":
            theta = (-spot * norm_pdf(d1) * sigma / (2 * math.sqrt(time_to_expiry)) 
                    - RISK_FREE_RATE * strike * math.exp(-RISK_FREE_RATE * time_to_expiry) * norm_cdf(d2))
        else:  # PE
            theta = (-spot * norm_pdf(d1) * sigma / (2 * math.sqrt(time_to_expiry)) 
                    + RISK_FREE_RATE * strike * math.exp(-RISK_FREE_RATE * time_to_expiry) * norm_cdf(-d2))
        
        theta = theta / 365  # Convert to daily theta
        
        # Vega (per 1% change in IV)
        vega = spot * norm_pdf(d1) * math.sqrt(time_to_expiry) / 100
        
        return (delta, gamma, theta, vega)
        
    except Exception as e:
        print(f"[GREEKS ERR] {e}")
        return (0.0, 0.0, 0.0, 0.0)

# =====================================================
# OPTIONS CHAIN FETCHING
# =====================================================

def fetch_options_chain(symbol: str) -> Dict:
    """Fetch options chain from Kite Connect"""
    try:
        # This is a placeholder - you'll need to implement actual Kite API call
        # For now, returning mock structure
        
        # In real implementation:
        # url = f"https://api.kite.trade/instruments/NFO/{symbol}"
        # response = requests.get(url, headers=KITE_HEADERS)
        # return response.json()
        
        print(f"[INFO] Fetching options chain for {symbol}")
        return {}
        
    except Exception as e:
        print(f"[OPTIONS FETCH ERR] {symbol}: {e}")
        return {}

# =====================================================
# PCR CALCULATION
# =====================================================

def calculate_pcr(options_data: List[OptionData]) -> Tuple[float, float]:
    """Calculate Put-Call Ratio for OI and Volume"""
    call_oi = sum(opt.oi for opt in options_data if opt.option_type == "CE")
    put_oi = sum(opt.oi for opt in options_data if opt.option_type == "PE")
    
    call_vol = sum(opt.volume for opt in options_data if opt.option_type == "CE")
    put_vol = sum(opt.volume for opt in options_data if opt.option_type == "PE")
    
    pcr_oi = put_oi / call_oi if call_oi > 0 else 0
    pcr_volume = put_vol / call_vol if call_vol > 0 else 0
    
    return pcr_oi, pcr_volume

# =====================================================
# MAX PAIN CALCULATION
# =====================================================

def calculate_max_pain(options_data: List[OptionData]) -> float:
    """
    Calculate Max Pain - the strike where option sellers face minimum loss
    """
    strikes = sorted(set(opt.strike for opt in options_data))
    
    min_pain = float('inf')
    max_pain_strike = 0
    
    for strike in strikes:
        total_pain = 0
        
        # Calculate pain for this strike
        for opt in options_data:
            if opt.option_type == "CE" and opt.strike < strike:
                # ITM calls
                total_pain += (strike - opt.strike) * opt.oi
            elif opt.option_type == "PE" and opt.strike > strike:
                # ITM puts
                total_pain += (opt.strike - strike) * opt.oi
        
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = strike
    
    return max_pain_strike

# =====================================================
# OI BUILD-UP ANALYSIS
# =====================================================

def analyze_oi_buildup(options_data: List[OptionData], spot_price: float) -> Tuple[List[float], List[float]]:
    """
    Detect bullish and bearish OI build-up
    
    Bullish: High Put writing (PE OI increase)
    Bearish: High Call writing (CE OI increase)
    """
    bullish_strikes = []
    bearish_strikes = []
    
    # Group by strike
    strike_data = {}
    for opt in options_data:
        if opt.strike not in strike_data:
            strike_data[opt.strike] = {"CE": None, "PE": None}
        strike_data[opt.strike][opt.option_type] = opt
    
    for strike, data in strike_data.items():
        ce = data.get("CE")
        pe = data.get("PE")
        
        # Bullish: High PE OI increase (Put writing)
        if pe and pe.oi_change > 1000:  # Threshold
            bullish_strikes.append(strike)
        
        # Bearish: High CE OI increase (Call writing)
        if ce and ce.oi_change > 1000:
            bearish_strikes.append(strike)
    
    return bullish_strikes[:5], bearish_strikes[:5]

# =====================================================
# SUPPORT/RESISTANCE FROM OI
# =====================================================

def identify_support_resistance(options_data: List[OptionData], spot_price: float) -> Tuple[List[float], List[float]]:
    """
    Identify support and resistance levels from OI concentration
    
    Support: Strikes with high Put OI (below spot)
    Resistance: Strikes with high Call OI (above spot)
    """
    # Get strikes with highest OI
    ce_strikes = [(opt.strike, opt.oi) for opt in options_data if opt.option_type == "CE"]
    pe_strikes = [(opt.strike, opt.oi) for opt in options_data if opt.option_type == "PE"]
    
    # Sort by OI
    ce_strikes.sort(key=lambda x: x[1], reverse=True)
    pe_strikes.sort(key=lambda x: x[1], reverse=True)
    
    # Resistance: High CE OI above spot
    resistance = [strike for strike, oi in ce_strikes[:5] if strike > spot_price]
    
    # Support: High PE OI below spot
    support = [strike for strike, oi in pe_strikes[:5] if strike < spot_price]
    
    return support[:3], resistance[:3]

# =====================================================
# MAIN ANALYSIS FUNCTION
# =====================================================

def analyze_options_chain(symbol: str, conn) -> Optional[OptionsChainAnalysis]:
    """Main options chain analysis"""
    try:
        # Fetch current spot price
        analytics_conn = sqlite3.connect(ANALYTICS_DB)
        analytics_conn.row_factory = sqlite3.Row
        cur = analytics_conn.cursor()
        
        cur.execute("""
            SELECT close FROM minute_analytics
            WHERE symbol = ?
            ORDER BY time_minute DESC
            LIMIT 1
        """, (symbol,))
        
        row = cur.fetchone()
        analytics_conn.close()
        
        if not row:
            return None
        
        spot_price = row['close']
        
        # Fetch options chain
        chain_data = fetch_options_chain(symbol)
        
        if not chain_data:
            print(f"[INFO] No options chain data for {symbol}")
            return None
        
        # Parse options data
        options_data = []
        # TODO: Parse actual chain data and create OptionData objects
        
        if not options_data:
            return None
        
        # Calculate metrics
        pcr_oi, pcr_volume = calculate_pcr(options_data)
        max_pain = calculate_max_pain(options_data)
        bullish_strikes, bearish_strikes = analyze_oi_buildup(options_data, spot_price)
        support, resistance = identify_support_resistance(options_data, spot_price)
        
        # Find ATM strike
        strike_gap = INDICES[symbol]["strike_gap"]
        atm_strike = round(spot_price / strike_gap) * strike_gap
        
        # Calculate totals
        call_oi = sum(opt.oi for opt in options_data if opt.option_type == "CE")
        put_oi = sum(opt.oi for opt in options_data if opt.option_type == "PE")
        call_vol = sum(opt.volume for opt in options_data if opt.option_type == "CE")
        put_vol = sum(opt.volume for opt in options_data if opt.option_type == "PE")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:00")
        
        analysis = OptionsChainAnalysis(
            timestamp=timestamp,
            symbol=symbol,
            spot_price=spot_price,
            atm_strike=atm_strike,
            pcr_oi=pcr_oi,
            pcr_volume=pcr_volume,
            max_pain=max_pain,
            call_oi_total=call_oi,
            put_oi_total=put_oi,
            call_vol_total=call_vol,
            put_vol_total=put_vol,
            bullish_strikes=bullish_strikes,
            bearish_strikes=bearish_strikes,
            resistance_levels=resistance,
            support_levels=support
        )
        
        # Save to database
        save_analysis(conn, analysis)
        
        return analysis
        
    except Exception as e:
        print(f"[OPTIONS ANALYSIS ERR] {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return None

# =====================================================
# SAVE ANALYSIS
# =====================================================

def save_analysis(conn, analysis: OptionsChainAnalysis):
    """Save options analysis to database"""
    try:
        cur = conn.cursor()
        
        # Generate analysis text
        analysis_text = generate_analysis_text(analysis)
        
        cur.execute("""
            INSERT INTO options_analysis
            (timestamp, symbol, spot_price, atm_strike,
             pcr_oi, pcr_volume, max_pain,
             call_oi_total, put_oi_total, call_vol_total, put_vol_total,
             bullish_strikes, bearish_strikes, resistance_levels, support_levels,
             analysis_text)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            analysis.timestamp, analysis.symbol, analysis.spot_price, analysis.atm_strike,
            analysis.pcr_oi, analysis.pcr_volume, analysis.max_pain,
            analysis.call_oi_total, analysis.put_oi_total, 
            analysis.call_vol_total, analysis.put_vol_total,
            json.dumps(analysis.bullish_strikes),
            json.dumps(analysis.bearish_strikes),
            json.dumps(analysis.resistance_levels),
            json.dumps(analysis.support_levels),
            analysis_text
        ))
        
        conn.commit()
        
    except Exception as e:
        print(f"[SAVE ERR] {e}")

# =====================================================
# GENERATE ANALYSIS TEXT
# =====================================================

def generate_analysis_text(analysis: OptionsChainAnalysis) -> str:
    """Generate human-readable analysis"""
    text = []
    
    # PCR Analysis
    if analysis.pcr_oi > 1.2:
        text.append("📈 PCR > 1.2: Bullish (Heavy Put buying)")
    elif analysis.pcr_oi < 0.8:
        text.append("📉 PCR < 0.8: Bearish (Heavy Call buying)")
    else:
        text.append("⚖️ PCR Neutral")
    
    # Max Pain
    if analysis.spot_price > analysis.max_pain:
        text.append(f"🎯 Max Pain: {analysis.max_pain} (Below spot - Bullish pressure)")
    else:
        text.append(f"🎯 Max Pain: {analysis.max_pain} (Above spot - Bearish pressure)")
    
    # Support/Resistance
    if analysis.support_levels:
        text.append(f"🛡️ Support: {', '.join(map(str, analysis.support_levels))}")
    if analysis.resistance_levels:
        text.append(f"🚧 Resistance: {', '.join(map(str, analysis.resistance_levels))}")
    
    return " | ".join(text)

# =====================================================
# MAIN LOOP
# =====================================================

def main():
    print("🚀 Options Chain Analyzer Started")
    print(f"📊 Tracking: {', '.join(INDICES.keys())}")
    
    conn = init_options_db()
    print("✅ Database initialized\n")
    
    while True:
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            for symbol in INDICES.keys():
                analysis = analyze_options_chain(symbol, conn)
                
                if analysis:
                    print(f"[{timestamp}] ✅ {symbol} - PCR: {analysis.pcr_oi:.2f} | Max Pain: {analysis.max_pain}")
            
            time.sleep(300)  # Update every 5 minutes
            
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(10)
    
    conn.close()

if __name__ == "__main__":
    main()
