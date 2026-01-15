#!/bin/bash
echo "🔍 Pre-flight checks..."

REQUIRED_FILES=(
  "access_token.txt"
  "api_key.txt"
  "telegram_token.txt"
  "chat_id.txt"
)

for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "❌ Missing required file: $file"
    exit 1
  fi
done

echo "✅ All required files found"




echo "🚀 Starting Professional Trading System..."

# Kill existing processes
echo "🔪 Killing existing processes..."
pkill -f tick_json_saver.py
pkill -f candle_builder_1m.py
pkill -f oi_category_builder.py
pkill -f comprehensive_analytics_engine.py
pkill -f alert_engine_pro.py
pkill -f api_server_step.py

sleep 2

# Start components in order
echo "📡 Starting Tick Capture..."
nohup python3 tick_json_saver.py > logs/tick_capture.log 2>&1 &
sleep 5

echo "🕯️ Starting Candle Builder..."
nohup python3 candle_builder_1m.py > logs/candle_builder.log 2>&1 &
sleep 5

echo "📊 Starting OI Analyzer..."
nohup python3 oi_category_builder.py > logs/oi_analyzer.log 2>&1 &
sleep 5

echo "🧠 Starting Analytics Engine..."
nohup python3 comprehensive_analytics_engine.py > logs/analytics.log 2>&1 &
sleep 10

echo "🚨 Starting Alert Engine..."
nohup python3 alert_engine_pro.py > logs/alerts.log 2>&1 &
sleep 5

echo "🌐 Starting API Server..."
nohup python3 api_server_step.py > logs/api_server.log 2>&1 &
sleep 3

# Verify all started
echo ""
echo "✅ System Status:"
echo "━━━━━━━━━━━━━━━━"

processes=(
    "tick_json_saver.py:Tick Capture"
    "candle_builder_1m.py:Candle Builder"
    "oi_category_builder.py:OI Analyzer"
    "comprehensive_analytics_engine.py:Analytics Engine"
    "alert_engine_pro.py:Alert Engine"
    "api_server_step.py:API Server"
)

for proc in "${processes[@]}"; do
    IFS=':' read -r script name <<< "$proc"
    if pgrep -f "$script" > /dev/null; then
        echo "✅ $name"
    else
        echo "❌ $name (FAILED)"
    fi
done

echo ""
echo "📱 Dashboard: http://localhost:8000"
echo "📊 API Docs: http://localhost:8000/docs"
echo "📱 Telegram: Check your bot for alerts"
echo ""
echo "🛑 To stop: ./stop_trading_system.sh"
