#!/bin/bash
# Professional Trading System - Shutdown Script
# ==============================================
# Gracefully stops all 6 pipeline processes

echo "🛑 Stopping Professional Trading System..."
echo ""

# Function to stop a process gracefully
stop_process() {
    local name=$1
    local pattern=$2
    
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        echo "⏳ Stopping $name..."
        pkill -TERM -f "$pattern"
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! pgrep -f "$pattern" > /dev/null 2>&1; then
                echo "✅ $name stopped"
                return 0
            fi
            sleep 1
        done
        
        # Force kill if still running
        if pgrep -f "$pattern" > /dev/null 2>&1; then
            echo "⚠️  Force killing $name..."
            pkill -9 -f "$pattern"
            sleep 1
            echo "✅ $name stopped (forced)"
        fi
    else
        echo "ℹ️  $name not running"
    fi
}

# Stop processes in reverse order (API first, tick capture last)
stop_process "API Server" "api_server.py"
stop_process "Alert Engine" "alert_engine_pro.py"
stop_process "Analytics Engine" "comprehensive_analytics_engine.py"
stop_process "OI Analyzer" "oi_category_builder_v2.py"
stop_process "Candle Builder" "candle_builder_1m.py"
stop_process "Tick Capture" "tick_json_saver.py"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All processes stopped successfully"
echo ""
echo "💡 Tip: Check logs in ./logs/ directory"
echo "🚀 To restart: ./start_trading_system.sh"
echo ""
