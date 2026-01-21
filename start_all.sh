#!/bin/bash
# Trading System - Complete Startup Script
# Starts all 6 backend processes automatically

echo "════════════════════════════════════════════════════════════"
echo "🚀 Trading System Startup"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check if screen is installed
if ! command -v screen &> /dev/null; then
    echo "❌ Screen not installed!"
    echo ""
    echo "Install command:"
    echo "  CentOS/RHEL: yum install screen -y"
    echo "  Ubuntu/Debian: apt install screen -y"
    echo ""
    exit 1
fi

# Check Telegram configuration
echo "📱 Checking Telegram configuration..."
python trading_secrets.py > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  WARNING: Telegram not configured!"
    echo "⚠️  Alerts will be logged but NOT sent to Telegram"
    echo ""
    echo "To configure:"
    echo "  1. Edit trading_secrets.py"
    echo "  2. Add your Bot Token and Chat ID"
    echo "  3. See QUICK_FIX_GUIDE.md for instructions"
    echo ""
    read -p "Continue without Telegram? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting..."
        exit 1
    fi
else
    echo "✅ Telegram configured"
fi

echo ""
echo "🛑 Stopping existing processes..."

# Kill existing screens gracefully
for session in tick candles oi analytics alerts api; do
    screen -S $session -X quit 2>/dev/null && echo "  Stopped: $session"
done

sleep 2
echo ""
echo "🚀 Starting processes..."
echo ""

# 1. Tick Data Saver
screen -dmS tick bash -c "python tick_json_saver.py 2>&1 | tee tick.log"
sleep 1
echo "✅ [1/6] Started: tick_json_saver.py"

# 2. Candle Builder
screen -dmS candles bash -c "python candle_builder_1m.py 2>&1 | tee candles.log"
sleep 1
echo "✅ [2/6] Started: candle_builder_1m.py"

# 3. OI Category Builder
screen -dmS oi bash -c "python oi_category_builder_v2.py 2>&1 | tee oi.log"
sleep 1
echo "✅ [3/6] Started: oi_category_builder_v2.py"

# 4. Comprehensive Analytics Engine (WITH NEW INDICATORS!)
screen -dmS analytics bash -c "python comprehensive_analytics_engine.py 2>&1 | tee analytics.log"
sleep 1
echo "✅ [4/6] Started: comprehensive_analytics_engine.py (25 indicators)"

# 5. Alert Engine (Telegram alerts)
screen -dmS alerts bash -c "python alert_engine_pro.py 2>&1 | tee alerts.log"
sleep 1
echo "✅ [5/6] Started: alert_engine_pro.py"

# 6. API Server (Dashboard backend)
screen -dmS api bash -c "python api_server.py 2>&1 | tee api.log"
sleep 2
echo "✅ [6/6] Started: api_server.py"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "🎉 All processes started successfully!"
echo "════════════════════════════════════════════════════════════"
echo ""

# Show screen sessions
echo "📋 Active Screen Sessions:"
screen -ls

echo ""
echo "════════════════════════════════════════════════════════════"
echo "📊 Access Points:"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  🌐 Dashboard:  http://localhost:8000"
echo "  🌐 From Remote: http://$(hostname -I | awk '{print $1}'):8000"
echo ""

echo "════════════════════════════════════════════════════════════"
echo "📖 Useful Commands:"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  View logs:"
echo "    screen -r tick       # Tick data collector"
echo "    screen -r analytics  # Analytics engine"
echo "    screen -r alerts     # Alert engine"
echo "    screen -r api        # API server"
echo ""
echo "  Detach from screen:"
echo "    Ctrl+A then D"
echo ""
echo "  View log files:"
echo "    tail -f analytics.log"
echo "    tail -f alerts.log"
echo ""
echo "  Stop all:"
echo "    ./stop_all.sh"
echo ""

echo "════════════════════════════════════════════════════════════"
echo "⏳ Waiting for initialization..."
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Please wait 2-3 minutes for:"
echo "  • Database creation"
echo "  • Data collection to start"
echo "  • First candles to build"
echo "  • Indicators to calculate"
echo ""
echo "Then check dashboard at: http://localhost:8000"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Startup Complete!"
echo "════════════════════════════════════════════════════════════"
