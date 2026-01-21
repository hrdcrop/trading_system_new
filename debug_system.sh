#!/bin/bash

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          🔍 TRADING SYSTEM DEBUG REPORT                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 1. Process Check
echo "1️⃣  RUNNING PROCESSES:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ps aux | grep -E "(tick_json|candle_builder|oi_category|analytics_engine|alert_engine|api_server)" | grep -v grep
echo ""

# 2. Database Check
echo "2️⃣  DATABASE STATUS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "tick_json_data.db" ]; then
    TICK_COUNT=$(sqlite3 tick_json_data.db "SELECT COUNT(*) FROM ticks_json" 2>/dev/null || echo "0")
    echo "✓ tick_json_data.db: $TICK_COUNT ticks"
else
    echo "✗ tick_json_data.db: NOT FOUND"
fi

if [ -f "market_data.db" ]; then
    CANDLE_COUNT=$(sqlite3 market_data.db "SELECT COUNT(*) FROM minute_candles" 2>/dev/null || echo "0")
    echo "✓ market_data.db (minute_candles): $CANDLE_COUNT rows"
    
    LATEST_CANDLE=$(sqlite3 market_data.db "SELECT time_minute FROM minute_candles ORDER BY time_minute DESC LIMIT 1" 2>/dev/null || echo "NONE")
    echo "  └─ Latest candle: $LATEST_CANDLE"
else
    echo "✗ market_data.db: NOT FOUND"
fi

if [ -f "market_analytics.db" ]; then
    ANALYTICS_COUNT=$(sqlite3 market_analytics.db "SELECT COUNT(*) FROM minute_analytics" 2>/dev/null || echo "0")
    echo "✓ market_analytics.db: $ANALYTICS_COUNT rows"
    
    LATEST_ANALYTICS=$(sqlite3 market_analytics.db "SELECT time_minute FROM minute_analytics ORDER BY time_minute DESC LIMIT 1" 2>/dev/null || echo "NONE")
    echo "  └─ Latest analytics: $LATEST_ANALYTICS"
else
    echo "✗ market_analytics.db: NOT FOUND"
fi

if [ -f "alerts_pro.db" ]; then
    ALERTS_COUNT=$(sqlite3 alerts_pro.db "SELECT COUNT(*) FROM alerts_final" 2>/dev/null || echo "0")
    echo "✓ alerts_pro.db: $ALERTS_COUNT alerts"
    
    LATEST_ALERT=$(sqlite3 alerts_pro.db "SELECT time, symbol, recommended_action FROM alerts_final ORDER BY id DESC LIMIT 1" 2>/dev/null || echo "NONE")
    echo "  └─ Latest alert: $LATEST_ALERT"
else
    echo "✗ alerts_pro.db: NOT FOUND"
fi

echo ""

# 3. API Server Check
echo "3️⃣  API SERVER STATUS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
API_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✓ API Server: RUNNING"
    echo "$API_HEALTH" | python3 -m json.tool 2>/dev/null || echo "$API_HEALTH"
else
    echo "✗ API Server: NOT RESPONDING"
fi
echo ""

# 4. Dashboard Check
echo "4️⃣  DASHBOARD ACCESS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DASHBOARD_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null)
if [ "$DASHBOARD_STATUS" = "200" ]; then
    echo "✓ Dashboard: ACCESSIBLE (HTTP $DASHBOARD_STATUS)"
else
    echo "✗ Dashboard: NOT ACCESSIBLE (HTTP $DASHBOARD_STATUS)"
fi
echo ""

# 5. Recent Logs
echo "5️⃣  RECENT LOG ERRORS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -d "logs" ]; then
    echo "📋 API Server Errors:"
    tail -10 logs/api_server.log 2>/dev/null | grep -i error || echo "  No errors found"
    echo ""
    
    echo "📋 Alert Engine Errors:"
    tail -10 logs/alert_engine.log 2>/dev/null | grep -i error || echo "  No errors found"
    echo ""
    
    echo "📋 Analytics Engine Errors:"
    tail -10 logs/analytics_engine.log 2>/dev/null | grep -i error || echo "  No errors found"
else
    echo "✗ logs/ directory not found"
fi

echo ""

# 6. Telegram Check
echo "6️⃣  TELEGRAM CONFIGURATION:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "trading_secrets.py" ]; then
    if grep -q "YOUR_BOT_TOKEN_HERE" trading_secrets.py 2>/dev/null; then
        echo "✗ Telegram: NOT CONFIGURED (placeholder values found)"
    else
        echo "✓ Telegram: CONFIGURED"
    fi
else
    echo "✗ trading_secrets.py: NOT FOUND"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    🎯 QUICK FIXES                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Recommendations
if [ "$CANDLE_COUNT" = "0" ] || [ "$ANALYTICS_COUNT" = "0" ]; then
    echo "⚠️  NO DATA IN DATABASES"
    echo "   → System might be starting for first time"
    echo "   → Wait 2-3 minutes for market hours"
    echo "   → Check if market is open (9:15 AM - 3:30 PM IST)"
    echo ""
fi

if ! pgrep -f "api_server.py" > /dev/null; then
    echo "⚠️  API SERVER NOT RUNNING"
    echo "   → Run: ./start_trading_system.sh"
    echo ""
fi

if ! pgrep -f "tick_json_saver.py" > /dev/null; then
    echo "⚠️  TICK CAPTURE NOT RUNNING"
    echo "   → Run: ./start_trading_system.sh"
    echo ""
fi

echo "📋 Next Steps:"
echo "   1. If no processes running: ./start_trading_system.sh"
echo "   2. Check full logs: tail -f logs/api_server.log"
echo "   3. Verify market hours: Monday-Friday 9:15 AM - 3:30 PM IST"
echo "   4. Test dashboard: http://localhost:8000"
echo ""
