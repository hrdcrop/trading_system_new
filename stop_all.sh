#!/bin/bash
# Trading System - Stop All Processes

echo "════════════════════════════════════════════════════════════"
echo "🛑 Stopping Trading System"
echo "════════════════════════════════════════════════════════════"
echo ""

# Stop all screen sessions
for session in tick candles oi analytics alerts api; do
    if screen -list | grep -q "\.$session"; then
        screen -S $session -X quit 2>/dev/null
        echo "✅ Stopped: $session"
    else
        echo "⚪ Not running: $session"
    fi
done

echo ""
echo "🔍 Checking for remaining Python processes..."
ps aux | grep python | grep -E "tick_json|candle_builder|oi_category|comprehensive|alert_engine|api_server" | grep -v grep

if [ $? -eq 0 ]; then
    echo ""
    echo "⚠️  Some processes still running. Force kill? (y/n)"
    read -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "tick_json_saver.py"
        pkill -f "candle_builder_1m.py"
        pkill -f "oi_category_builder_v2.py"
        pkill -f "comprehensive_analytics_engine.py"
        pkill -f "alert_engine_pro.py"
        pkill -f "api_server.py"
        echo "✅ Force killed all processes"
    fi
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ All processes stopped"
echo "════════════════════════════════════════════════════════════"
