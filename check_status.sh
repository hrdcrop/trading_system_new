#!/bin/bash

echo "📊 TRADING SYSTEM STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

processes=(
    "tick_json_saver.py:Tick Capture"
    "candle_builder_1m.py:Candle Builder"
    "oi_category_builder_v2.py:OI Analyzer"
    "comprehensive_analytics_engine.py:Analytics Engine"
    "alert_engine_pro.py:Alert Engine"
    "api_server.py:API Server"
)

running=0
stopped=0

for proc in "${processes[@]}"; do
    IFS=':' read -r script name <<< "$proc"
    if pgrep -f "$script" > /dev/null; then
        echo "✅ $name - RUNNING"
        ((running++))
    else
        echo "❌ $name - STOPPED"
        ((stopped++))
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Running: $running | Stopped: $stopped"
echo ""

if [ $running -eq 6 ]; then
    echo "🟢 System Status: ALL SERVICES RUNNING"
elif [ $running -eq 0 ]; then
    echo "🔴 System Status: ALL SERVICES STOPPED"
else
    echo "🟡 System Status: PARTIAL (Some services down)"
fi

echo ""
echo "📱 Dashboard: http://localhost:8000"
