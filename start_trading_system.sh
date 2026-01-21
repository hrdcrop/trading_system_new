#!/bin/bash

# Professional Trading System - Startup Script (FIXED)
# =====================================================
# Starts all 6 pipeline processes as persistent daemons

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔍 Pre-flight checks..."

# Check required files
REQUIRED_FILES=(
    "tick_json_saver.py"
    "candle_builder_1m.py"
    "oi_category_builder_v2.py"
    "comprehensive_analytics_engine.py"
    "alert_engine_pro.py"
    "api_server.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
done

echo "✅ All required files found"

echo ""
echo "🚀 Starting Professional Trading System..."

# Kill existing processes
echo "🔪 Killing existing processes..."
pkill -f "tick_json_saver.py" 2>/dev/null
pkill -f "candle_builder_1m" 2>/dev/null
pkill -f "oi_category_builder_v2" 2>/dev/null
pkill -f "comprehensive_analytics_engine.py" 2>/dev/null
pkill -f "alert_engine_pro.py" 2>/dev/null
pkill -f "api_server.py" 2>/dev/null
sleep 2

# Migrate databases if needed
echo "🔄 Checking database schema..."

# Migration for alerts_pro.db (telegram_sent column)
if [ -f "alerts_pro.db" ]; then
    echo "🔄 Migrating alerts_pro.db..."
    python3 << 'EOF'
import sqlite3
conn = sqlite3.connect("alerts_pro.db")
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE alerts ADD COLUMN telegram_sent INTEGER DEFAULT 0")
    cursor.execute("UPDATE alerts SET telegram_sent = 0")
    conn.commit()
    print("✅ Migration complete!")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e):
        print("✅ telegram_sent column already exists")
        cursor.execute("UPDATE alerts SET telegram_sent = 0 WHERE telegram_sent IS NULL")
        conn.commit()
        print("✅ Updated existing rows")
    else:
        print(f"❌ Migration error: {e}")
conn.close()
EOF
fi

# Start all processes in background

echo "📡 Starting Tick Capture..."
nohup python3 -u tick_json_saver.py > logs/tick_json_saver.log 2>&1 &
TICK_PID=$!
sleep 1

echo "🕯️ Starting Candle Builder (Daemon Mode)..."
nohup python3 -u candle_builder_1m.py > logs/candle_builder.log 2>&1 &
CANDLE_PID=$!
sleep 1

echo "📊 Starting OI Analyzer (Daemon Mode)..."
nohup python3 -u oi_category_builder_v2.py > logs/oi_analyzer.log 2>&1 &
OI_PID=$!
sleep 1

echo "🧠 Starting Analytics Engine..."
nohup python3 -u comprehensive_analytics_engine.py > logs/analytics_engine.log 2>&1 &
ANALYTICS_PID=$!
sleep 1

echo "🚨 Starting Alert Engine..."
nohup python3 -u alert_engine_pro.py > logs/alert_engine.log 2>&1 &
ALERT_PID=$!
sleep 1

echo "🌐 Starting API Server..."
nohup python3 -u api_server.py > logs/api_server.log 2>&1 &
API_PID=$!
sleep 2

# Verify processes are still running
echo ""
echo "✅ System Status:"
echo "━━━━━━━━━━━━━━━━"

check_process() {
    local name=$1
    local pattern=$2
    
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        echo "✅ $name"
        return 0
    else
        echo "❌ $name (FAILED)"
        return 1
    fi
}

check_process "Tick Capture" "tick_json_saver.py"
check_process "Candle Builder" "candle_builder_1m.py"
check_process "OI Analyzer" "oi_category_builder_v2.py"
check_process "Analytics Engine" "comprehensive_analytics_engine.py"
check_process "Alert Engine" "alert_engine_pro.py"
check_process "API Server" "api_server.py"

echo ""
echo "📱 Dashboard: http://localhost:8000"
echo "📊 API Docs: http://localhost:8000/docs"
echo "📱 Telegram: Check your bot for alerts"
echo ""
echo "🛑 To stop: ./stop_trading_system.sh"
