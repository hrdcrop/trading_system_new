#!/bin/bash
# Trading System - Status Check Script

echo "════════════════════════════════════════════════════════════"
echo "📊 Trading System Status Check"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check Telegram Configuration
echo "1️⃣  Telegram Configuration:"
python trading_secrets.py 2>&1 | head -3
echo ""

# Check Running Processes
echo "2️⃣  Running Processes:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

processes=("tick_json_saver" "candle_builder" "oi_category_builder" "comprehensive_analytics" "alert_engine_pro" "api_server")
all_running=true

for proc in "${processes[@]}"; do
    if ps aux | grep python | grep -q "$proc"; then
        echo "  ✅ $proc.py"
    else
        echo "  ❌ $proc.py (NOT RUNNING)"
        all_running=false
    fi
done
echo ""

# Check Database Files
echo "3️⃣  Database Files:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

databases=("tick_json_data.db" "minute_candles.db" "oi_analysis.db" "market_analytics.db" "alerts_pro.db")

for db in "${databases[@]}"; do
    if [ -f "$db" ]; then
        size=$(ls -lh "$db" | awk '{print $5}')
        echo "  ✅ $db ($size)"
    else
        echo "  ❌ $db (NOT FOUND)"
    fi
done
echo ""

# Summary
echo "════════════════════════════════════════════════════════════"
if $all_running && [ -f "market_analytics.db" ]; then
    echo "  ✅ System Status: OPERATIONAL 🎉"
else
    echo "  ⚠️  System Status: INCOMPLETE"
    echo "  Run: ./start_all.sh"
fi
echo "════════════════════════════════════════════════════════════"
