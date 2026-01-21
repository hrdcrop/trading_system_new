#!/bin/bash

echo "🔄 Restarting API Server with fresh table schema..."

# Stop API server
pkill -f "api_server.py"
sleep 2

# Verify table schema
echo "📊 Verifying table schema..."
sqlite3 market_data.db "PRAGMA table_info(minute_candles)" | grep symbol
if [ $? -eq 0 ]; then
    echo "✅ Symbol column exists"
else
    echo "❌ Symbol column missing!"
    exit 1
fi

# Clear cache and restart
> logs/api_server.log

echo "🚀 Starting API server..."
nohup python3 -u api_server.py > logs/api_server.log 2>&1 &

# Wait for startup
sleep 5

# Test endpoints
echo ""
echo "🧪 Testing endpoints..."
echo ""

# Test 1: Health
echo "1. Health Check:"
curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null && echo "✅ OK" || echo "❌ Failed"

# Test 2: Market Latest
echo "2. Market Latest:"
MARKET_RESPONSE=$(curl -s http://localhost:8000/market/latest)
if echo "$MARKET_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} symbols')" 2>/dev/null; then
    echo "✅ OK"
else
    echo "❌ Failed - checking logs..."
    tail -10 logs/api_server.log | grep -i error
fi

# Test 3: BANKNIFTY Candles
echo "3. BANKNIFTY Candles:"
CANDLES_RESPONSE=$(curl -s "http://localhost:8000/timeseries/candles/BANKNIFTY?hours=1")
if echo "$CANDLES_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} candles')" 2>/dev/null; then
    echo "✅ OK"
else
    echo "❌ Failed"
fi

# Test 4: Analytics
echo "4. Analytics Latest:"
ANALYTICS_RESPONSE=$(curl -s http://localhost:8000/analytics/latest)
if echo "$ANALYTICS_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} rows')" 2>/dev/null; then
    echo "✅ OK"
else
    echo "❌ Failed"
fi

# Test 5: Alerts
echo "5. Alerts Latest:"
curl -s http://localhost:8000/alerts/latest | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} alerts')" 2>/dev/null && echo "✅ OK" || echo "❌ Failed"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              ✅ API SERVER RESTARTED                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Dashboard: http://localhost:8000"
echo "📊 API Docs: http://localhost:8000/docs"
echo ""
echo "🔍 Monitor: tail -f logs/api_server.log"
echo ""
