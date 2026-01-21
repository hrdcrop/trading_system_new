# Trading System - Complete Setup & Usage Guide
## ट्रेडिंग सिस्टम - पूरी सेटअप और उपयोग गाइड

---

## 📋 Table of Contents / विषय सूची

1. [Issues Fixed / ठीक की गई समस्याएं](#issues-fixed)
2. [New Indicators Added / नए संकेतक जोड़े गए](#new-indicators)
3. [System Architecture / सिस्टम संरचना](#system-architecture)
4. [Setup Instructions / सेटअप निर्देश](#setup-instructions)
5. [How to Run / कैसे चलाएं](#how-to-run)
6. [Telegram Integration / टेलीग्राम एकीकरण](#telegram-integration)
7. [Dashboard Access / डैशबोर्ड एक्सेस](#dashboard-access)
8. [Troubleshooting / समस्या निवारण](#troubleshooting)

---

## 🔧 Issues Fixed / ठीक की गई समस्याएं

### 1. **Dashboard Par Alerts Nahi Aa Rahe The**
   - **Problem**: `alerts_pro.db` database missing hone par API server crash ho jata tha
   - **Solution**: API server mein graceful error handling add ki
     - Database missing ho to empty array `[]` return karta hai
     - Dashboard properly load hota hai alerts ke bina bhi

### 2. **Telegram Par Alerts Nahi Ja Rahe The**
   - **Problem**: `trading_secrets.py` file missing thi
   - **Solution**:
     - Naya file `trading_secrets.py` banaya gaya
     - Telegram bot token aur chat ID configuration ke liye
     - Instructions included hai setup ke liye

### 3. **Charts Nahi Aa Rahe The**
   - **Root Cause**: Backend processes (tick_json_saver, candle_builder, etc.) nahi chal rahe the
   - **Solution**: Complete pipeline setup instructions added

---

## 🆕 New Indicators Added / नए संकेतक जोड़े गए

Aapke reference program se inspired hokar, maine ye naye indicators add kiye hain:

### 1. **SMMA (Smoothed Moving Average)**
   - **Periods**: 7 and 25
   - **Purpose**: Trend identification with less noise than regular MA
   - **Formula**: SMMA = (SMMA_prev * (n-1) + current_price) / n
   - **Signal**:
     - SMMA से ऊपर price = Bullish (+1)
     - SMMA से नीचे price = Bearish (-1)

### 2. **LSMA (Least Squares Moving Average / Linear Regression)**
   - **Periods**: 7 and 25
   - **Offset**: 0 (configurable)
   - **Purpose**: Forward-looking trend indicator using linear regression
   - **Signal**:
     - LSMA से ऊपर price = Bullish (+1)
     - LSMA से नीचे price = Bearish (-1)

### 3. **EMA Crossover Detection (9/26)**
   - **Fast EMA**: 9 periods
   - **Slow EMA**: 26 periods
   - **Signals**:
     - `+1`: Bullish crossover (9 EMA crosses above 26 EMA) - **BUY SIGNAL**
     - `-1`: Bearish crossover (9 EMA crosses below 26 EMA) - **SELL SIGNAL**
     - `0`: No crossover

### 4. **Existing Indicators Enhanced**
   - **MACD**: Already present (12, 26, 9) - ab properly configured
   - **EMA 9**: Already calculated
   - Total indicators ab **25** ho gaye hain (21 purane + 4 naye signals)

---

## 🏗️ System Architecture / सिस्टम संरचना

```
┌─────────────────────────────────────────────────────────────┐
│ DATA COLLECTION PIPELINE                                     │
└─────────────────────────────────────────────────────────────┘

1️⃣ tick_json_saver.py
   ├─ Kite WebSocket se live tick data fetch karta hai
   ├─ Database: tick_json_data.db
   └─ Output: Raw ticks with bid/ask depth

         ↓

2️⃣ candle_builder_1m.py
   ├─ Ticks ko 1-minute candles mein convert karta hai
   ├─ Database: minute_candles.db
   └─ Output: OHLCV + depth metrics

         ↓

3️⃣ oi_category_builder_v2.py
   ├─ Open Interest analysis (LB, SB, SC, LU)
   ├─ Database: oi_analysis.db
   └─ Only for futures (BANKNIFTY, NIFTY)

         ↓

4️⃣ comprehensive_analytics_engine.py ⭐ (UPDATED)
   ├─ 25 indicators calculate karta hai
   ├─ Database: market_analytics.db
   ├─ NEW: SMMA, LSMA, EMA Crossover
   └─ Output: Complete analytics per minute

         ↓

5️⃣ alert_engine_pro.py
   ├─ High-quality alerts generate karta hai
   ├─ Database: alerts_pro.db
   ├─ Confidence scoring (0-100)
   └─ Output: A+/A grade alerts to Telegram

         ↓

6️⃣ api_server.py (FastAPI) ⭐ (FIXED)
   ├─ REST API endpoints provide karta hai
   ├─ Port: 8000
   ├─ Fixed: Graceful error handling for missing DB
   └─ Serves data to dashboard

         ↓

7️⃣ trading_dashboard_pro.html
   ├─ Real-time charts aur alerts display
   ├─ Browser mein khulta hai
   └─ Auto-refresh every 30 seconds
```

---

## 🚀 Setup Instructions / सेटअप निर्देश

### Step 1: Telegram Bot Setup (IMPORTANT!)

#### A. BotFather se Bot Banao

1. Telegram app kholo
2. Search karo: `@BotFather`
3. Send karo: `/newbot`
4. Bot ka naam do (example: "My Trading Bot")
5. Username do (example: "mytradingbot123_bot")
6. **Token copy karo** - dikhega aise: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

#### B. Chat ID Nikalo

1. Apne bot ko start karo (uska username search karke)
2. Koi bhi message bhejo
3. Browser mein jao:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   (Replace `<YOUR_BOT_TOKEN>` with your actual token)
4. JSON response mein dhundo: `"chat":{"id":123456789}`
5. **Ye ID copy karo**

#### C. trading_secrets.py Update Karo

```bash
nano trading_secrets.py
```

Replace karo:
```python
TELEGRAM_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"  # Apna token
CHAT_ID = "123456789"  # Apni chat ID
```

Save karo: `Ctrl+X`, phir `Y`, phir `Enter`

### Step 2: Verify Configuration

```bash
python trading_secrets.py
```

Output milna chahiye:
```
✅ Telegram configuration is valid
✅ Bot Token: 123456789:...
✅ Chat ID: 123456789
```

---

## ▶️ How to Run / कैसे चलाएं

### Option 1: Complete System Start (Recommended)

Ek-ek karke sab processes start karo (alag-alag terminals mein):

```bash
# Terminal 1: Tick Data Collection
python tick_json_saver.py

# Terminal 2: Candle Building
python candle_builder_1m.py

# Terminal 3: OI Analysis
python oi_category_builder_v2.py

# Terminal 4: Analytics Engine (With NEW indicators!)
python comprehensive_analytics_engine.py

# Terminal 5: Alert Engine (Telegram alerts)
python alert_engine_pro.py

# Terminal 6: API Server (Dashboard backend)
python api_server.py
```

### Option 2: Screen/Tmux Use Karo (Production)

```bash
# Screen sessions banao
screen -S tick_saver
python tick_json_saver.py
# Ctrl+A then D to detach

screen -S candle_builder
python candle_builder_1m.py
# Ctrl+A then D

screen -S analytics
python comprehensive_analytics_engine.py
# Ctrl+A then D

screen -S alerts
python alert_engine_pro.py
# Ctrl+A then D

screen -S api
python api_server.py
# Ctrl+A then D

# Check all screens
screen -ls

# Reattach to any screen
screen -r tick_saver
```

---

## 📱 Telegram Integration / टेलीग्राम एकीकरण

### Alert Quality Levels

| Grade | Confidence | Telegram? | Priority |
|-------|-----------|-----------|----------|
| A+ | ≥80% | ✅ Yes | 🔴 HIGH |
| A | 70-79% | ✅ Yes | 🟡 MEDIUM |
| B | 60-69% | ❌ No | ⚪ LOGGED ONLY |
| SKIP | <60% | ❌ No | - |

### Alert Format Example

```
🔴 A+ GRADE ALERT
🟢 BANKNIFTY | BUY_CE

⏰ 14:30
📊 CONFIDENCE: 85%

🎯 WHY THIS ALERT:
• Strong LB (Long Built) with +15000 OI
• Buyer dominant depth (ratio 2.3)
• Banking sector aligned bullish
• TRENDING_UP regime

📈 MARKET CONTEXT:
• OI: LB (Long Built)
• Depth: Buyer Dominant
• Sector: BANKING BUY, NBFC BUY
• Index: BULLISH
• Regime: TRENDING_UP
• VIX: 14.2 (NORMAL)

🏷️ Type: TREND_CONTINUATION

💡 NEW INDICATORS:
• SMMA 7/25: Bullish alignment
• LSMA 7/25: Uptrend confirmed
• EMA 9/26 Crossover: Bullish (+1)
```

---

## 🖥️ Dashboard Access / डैशबोर्ड एक्सेस

### Start Dashboard

1. API server running hona chahiye:
   ```bash
   python api_server.py
   ```
   Output: `INFO: Uvicorn running on http://0.0.0.0:8000`

2. Browser mein kholo:
   ```
   http://localhost:8000
   ```
   या
   ```
   http://your-server-ip:8000
   ```

### Dashboard Features

✅ **Real-time Charts**
   - Candlestick charts with 25 indicators
   - NEW: SMMA, LSMA overlay
   - EMA crossover markers

✅ **Alert Panel** (Right side)
   - Latest high-quality alerts
   - Confidence scores
   - Action recommendations

✅ **Indicator Panel**
   - All 25 indicators with values
   - Bullish/Bearish percentages
   - Signal count

✅ **Market Direction**
   - BANKNIFTY, NIFTY, FinNifty
   - Sector analysis
   - VIX state

---

## 🐛 Troubleshooting / समस्या निवारण

### Problem 1: "Telegram alerts nahi aa rahe"

**Check:**
```bash
python trading_secrets.py
```

**Solutions:**
- ❌ `Configuration incomplete` → Update `TELEGRAM_TOKEN` and `CHAT_ID`
- ✅ `Configuration is valid` → Check if `alert_engine_pro.py` running hai

### Problem 2: "Dashboard par data nahi aa raha"

**Check:**
1. API server running?
   ```bash
   ps aux | grep api_server
   ```

2. Database files exist?
   ```bash
   ls -lh *.db
   ```
   Required files:
   - `tick_json_data.db`
   - `minute_candles.db`
   - `oi_analysis.db`
   - `market_analytics.db`
   - `alerts_pro.db`

3. Check API endpoints:
   ```bash
   curl http://localhost:8000/market/latest
   curl http://localhost:8000/alerts/latest
   ```

### Problem 3: "Charts nahi ban rahe"

**Check pipeline sequence:**
```bash
# All should be running:
ps aux | grep tick_json_saver
ps aux | grep candle_builder
ps aux | grep comprehensive_analytics
```

**Start missing processes** (see "How to Run" section)

### Problem 4: "New indicators nahi dikh rahe"

**Solution: Database schema update karo**
```bash
# Delete old database (BACKUP FIRST!)
mv market_analytics.db market_analytics.db.backup

# Restart analytics engine (will recreate with new schema)
python comprehensive_analytics_engine.py
```

### Problem 5: "Database locked" error

**Solution:**
```bash
# Find processes using database
lsof *.db

# Kill duplicate processes
pkill -f comprehensive_analytics
pkill -f alert_engine

# Restart cleanly
python comprehensive_analytics_engine.py
```

---

## 📊 Indicator Reference / संकेतक संदर्भ

### All 25 Indicators

| # | Indicator | Type | Period | Signal |
|---|-----------|------|--------|--------|
| 1 | EMA 9 | Trend | 9 | Price vs EMA |
| 2 | EMA 21 | Trend | 21 | Price vs EMA |
| 3 | EMA 50 | Trend | 50 | Price vs EMA |
| 4 | EMA 200 | Trend | 200 | Price vs EMA |
| 5 | MACD | Momentum | 12,26,9 | Histogram sign |
| 6 | ADX Trend | Trend Strength | 14 | >25 + direction |
| 7 | Kalman Filter | Adaptive | - | Prediction |
| 8 | RSI | Momentum | 14 | <30 or >70 |
| 9 | Stochastic | Momentum | 14 | <20 or >80 |
| 10 | CCI | Momentum | 20 | <-100 or >100 |
| 11 | MFI | Volume | 14 | <20 or >80 |
| 12 | ROC | Momentum | 12 | +/- |
| 13 | Bollinger Bands | Volatility | 20 | Touch bands |
| 14 | ATR Trend | Volatility | 14 | High vol + trend |
| 15 | VWAP | Volume | - | Price vs VWAP |
| 16 | Volume Trend | Volume | 5/20 | Spike + direction |
| 17 | OBV | Volume | - | +/- |
| 18 | OI Signal | Futures | - | LB/SB/SC/LU |
| 19 | Depth Signal | Order Book | - | Buyer/Seller |
| 20 | Pattern | Candlestick | 3 | Engulfing, etc |
| 21 | Regime | Market Phase | 50 | Trend/Range/Vol |
| 22 | **SMMA 7** 🆕 | **Trend** | **7** | **Price vs SMMA** |
| 23 | **SMMA 25** 🆕 | **Trend** | **25** | **Price vs SMMA** |
| 24 | **LSMA 7** 🆕 | **Regression** | **7** | **Price vs LSMA** |
| 25 | **LSMA 25** 🆕 | **Regression** | **25** | **Price vs LSMA** |
| ⭐ | **EMA Cross 9/26** 🆕 | **Crossover** | **9, 26** | **+1/-1/0** |

---

## 🎯 Trading Strategy with NEW Indicators

### Entry Signals (BUY CE / SELL PE)

**High Confidence Setup (>80%):**
```
✅ OI Category: LB or SC
✅ Depth: Buyer Dominant
✅ EMA 9/26 Crossover: Bullish (+1) 🆕
✅ SMMA 7 > SMMA 25 🆕
✅ LSMA pointing up 🆕
✅ Price > EMA 9 > EMA 21
✅ MACD: Positive histogram
✅ Sector: Banking + NBFC Bullish
✅ Regime: TRENDING_UP
```

**Exit Signals:**
```
❌ EMA 9/26 Bearish Crossover (-1) 🆕
❌ Price < SMMA 7 🆕
❌ LSMA turns down 🆕
❌ OI Category reverses (LU or SB)
❌ Depth turns Seller Dominant
```

### Advanced Filtering

**SMMA Ribbon Filter:**
- SMMA 7 > SMMA 25 = Strong uptrend
- SMMA 7 < SMMA 25 = Strong downtrend
- SMMA crossing = Trend change

**LSMA Forecast:**
- LSMA slope angle > 45° = Strong momentum
- LSMA slope angle < 15° = Weak momentum
- Use for target projections

---

## 📝 Important Notes / महत्वपूर्ण नोट्स

1. **Market Hours**: System 9:15 AM - 3:30 PM IST ko automatically data collect karega

2. **Database Size**: Regular backups lo, especially `market_analytics.db` (grows fast)

3. **Server Requirements**:
   - RAM: Minimum 2GB
   - Storage: 10GB free space
   - Network: Stable internet for Kite WebSocket

4. **API Limits**: Zerodha Kite API rate limits ka dhyan rakho

5. **Testing**: Paper trading se start karo, phir real money mein jao

---

## 🆘 Support

### GitHub Issues
```
https://github.com/hrdcrop/trading_system_new/issues
```

### Database Inspection
```bash
# Check alerts
sqlite3 alerts_pro.db "SELECT * FROM alerts_final ORDER BY id DESC LIMIT 10;"

# Check analytics
sqlite3 market_analytics.db "SELECT time_minute, symbol, ema_crossover_9_26, smma_7_value, lsma_7_value FROM minute_analytics WHERE symbol='BANKNIFTY' ORDER BY time_minute DESC LIMIT 10;"
```

---

## ✅ Quick Checklist / जल्दी चेकलिस्ट

Before starting trading:

- [ ] `trading_secrets.py` configured with Telegram credentials
- [ ] Test Telegram bot (send message manually)
- [ ] All 6 processes running (tick_saver to api_server)
- [ ] Dashboard accessible at `http://localhost:8000`
- [ ] Alerts showing in Telegram
- [ ] New indicators visible in dashboard (SMMA, LSMA, EMA Cross)
- [ ] Database files created and updating
- [ ] Market hours active (9:15-15:30 IST)

---

## 🎉 Success!

Agar sab kuch theek se setup ho gaya, to aapko:
1. ✅ Dashboard par live charts dikhengi
2. ✅ Telegram par high-quality alerts aayengi
3. ✅ Naye indicators (SMMA, LSMA, EMA Cross) kaam karengi
4. ✅ Confidence scores har alert ke saath
5. ✅ Real-time market analysis

**Happy Trading! 🚀📈**

---

*Last Updated: 2026-01-21*
*Version: 3.0 with NEW INDICATORS*
