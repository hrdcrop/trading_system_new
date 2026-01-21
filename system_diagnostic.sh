#!/bin/bash

echo "════════════════════════════════════════════════════════════════"
echo "🔍 TRADING SYSTEM COMPLETE DIAGNOSTIC"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. FILE STRUCTURE CHECK
echo "📁 FILE STRUCTURE CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━"
REQUIRED_FILES=(
    "tick_json_saver.py"
    "candle_builder_1m.py"
    "oi_category_builder_v2.py"
    "comprehensive_analytics_engine.py"
    "alert_engine_pro.py"
    "api_server.py"
    "init_db.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} $file"
    else
        echo -e "${RED}❌${NC} $file (MISSING)"
    fi
done
echo ""

# 2. DATABASE CHECK
echo "💾 DATABASE STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━"
for db in market_data.db alerts_pro.db; do
    if [ -f "$db" ]; then
        SIZE=$(ls -lh "$db" | awk '{print $5}')
        echo -e "${GREEN}✅${NC} $db (Size: $SIZE)"
    else
        echo -e "${RED}❌${NC} $db (NOT FOUND)"
    fi
done
echo ""

# 3. DATABASE TABLES CHECK
echo "📊 DATABASE TABLES (market_data.db)"
echo "━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "market_data.db" ]; then
    TABLES=$(sqlite3 market_data.db ".tables" 2>&1)
    if [ -z "$TABLES" ]; then
        echo -e "${RED}❌ NO TABLES FOUND - DATABASE EMPTY!${NC}"
    else
        echo "$TABLES"
        echo ""
        echo "Row counts:"
        for table in candles_1m oi_categories comprehensive_analytics; do
            COUNT=$(sqlite3 market_data.db "SELECT COUNT(*) FROM $table" 2>/dev/null || echo "0")
            echo "  $table: $COUNT rows"
        done
    fi
else
    echo -e "${RED}❌ market_data.db not found${NC}"
fi
echo ""

echo "📊 DATABASE TABLES (alerts_pro.db)"
echo "━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "alerts_pro.db" ]; then
    TABLES=$(sqlite3 alerts_pro.db ".tables" 2>&1)
    if [ -z "$TABLES" ]; then
        echo -e "${RED}❌ NO TABLES FOUND${NC}"
    else
        echo "$TABLES"
        echo ""
        # Check for correct table name
        if sqlite3 alerts_pro.db "SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'" | grep -q "alerts"; then
            echo -e "${GREEN}✅${NC} 'alerts' table exists"
        elif sqlite3 alerts_pro.db "SELECT name FROM sqlite_master WHERE type='table' AND name='alerts_final'" | grep -q "alerts_final"; then
            echo -e "${YELLOW}⚠️${NC} 'alerts_final' table exists (should be 'alerts')"
        else
            echo -e "${RED}❌${NC} No alerts table found"
        fi
    fi
else
    echo -e "${RED}❌ alerts_pro.db not found${NC}"
fi
echo ""

# 4. PROCESS STATUS
echo "⚙️  RUNNING PROCESSES"
echo "━━━━━━━━━━━━━━━━━━━━━━"
PROCESSES=(
    "tick_json_saver.py:Tick Capture"
    "candle_builder_1m:Candle Builder"
    "oi_category_builder_v2:OI Analyzer"
    "comprehensive_analytics_engine:Analytics Engine"
    "alert_engine_pro:Alert Engine"
    "api_server.py:API Server"
)

for proc in "${PROCESSES[@]}"; do
    IFS=':' read -r pattern name <<< "$proc"
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        PID=$(pgrep -f "$pattern")
        echo -e "${GREEN}✅${NC} $name (PID: $PID)"
    else
        echo -e "${RED}❌${NC} $name (NOT RUNNING)"
    fi
done
echo ""

# 5. RECENT DATA CHECK
echo "📈 RECENT DATA CHECK (Last 5 minutes)"
echo "━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "market_data.db" ]; then
    RECENT=$(sqlite3 market_data.db "SELECT COUNT(*) FROM candles_1m WHERE timestamp > datetime('now', '-5 minutes')" 2>/dev/null || echo "0")
    if [ "$RECENT" -gt 0 ]; then
        echo -e "${GREEN}✅${NC} $RECENT fresh candles in last 5 min"
        echo ""
        echo "Latest candles:"
        sqlite3 market_data.db "SELECT symbol, timestamp, close FROM candles_1m ORDER BY timestamp DESC LIMIT 5" 2>/dev/null || echo "Error reading data"
    else
        echo -e "${YELLOW}⚠️${NC} No fresh data in last 5 minutes"
        echo ""
        echo "Latest data timestamp:"
        sqlite3 market_data.db "SELECT symbol, MAX(timestamp) as latest FROM candles_1m GROUP BY symbol LIMIT 5" 2>/dev/null || echo "No data"
    fi
else
    echo -e "${RED}❌${NC} Cannot check - database missing"
fi
echo ""

# 6. TICK DATA CHECK
echo "📡 TICK DATA FILES"
echo "━━━━━━━━━━━━━━━━━━━━━━"
if [ -d "tick_data" ]; then
    FILE_COUNT=$(ls -1 tick_data/*.json 2>/dev/null | wc -l)
    echo "Total JSON files: $FILE_COUNT"
    echo ""
    echo "Most recent files:"
    ls -lth tick_data/*.json 2>/dev/null | head -5 || echo "No JSON files found"
else
    echo -e "${RED}❌${NC} tick_data/ directory not found"
fi
echo ""

# 7. LOG FILE CHECK
echo "📝 LOG FILES STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━"
if [ -d "logs" ]; then
    for log in tick_json_saver.log candle_builder.log oi_analyzer.log analytics_engine.log alert_engine.log api_server.log; do
        if [ -f "logs/$log" ]; then
            SIZE=$(ls -lh "logs/$log" | awk '{print $5}')
            LINES=$(wc -l < "logs/$log")
            echo "  $log: $SIZE ($LINES lines)"
        else
            echo -e "  ${YELLOW}⚠️${NC} $log: NOT FOUND"
        fi
    done
else
    echo -e "${RED}❌${NC} logs/ directory not found"
fi
echo ""

# 8. LATEST LOG ERRORS
echo "🚨 RECENT LOG ERRORS (Last 10 lines)"
echo "━━━━━━━━━━━━━━━━━━━━━━"
if [ -d "logs" ]; then
    for log in logs/*.log; do
        if [ -f "$log" ]; then
            ERRORS=$(tail -20 "$log" | grep -iE "error|exception|failed|traceback" | head -3)
            if [ ! -z "$ERRORS" ]; then
                echo "$(basename $log):"
                echo "$ERRORS"
                echo ""
            fi
        fi
    done
else
    echo "No logs directory"
fi
echo ""

# 9. API SERVER CHECK
echo "🌐 API SERVER STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC} API Server responding at http://localhost:8000"
    echo ""
    echo "Testing endpoints:"
    CANDLES=$(curl -s http://localhost:8000/api/latest-candles | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "  /api/latest-candles: $CANDLES instruments"
    
    ALERTS=$(curl -s http://localhost:8000/api/recent-alerts | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "  /api/recent-alerts: $ALERTS alerts"
else
    echo -e "${RED}❌${NC} API Server not responding"
fi
echo ""

# 10. MARKET HOURS CHECK
echo "🕐 CURRENT TIME & MARKET STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━"
CURRENT_TIME=$(date +"%H:%M")
CURRENT_DAY=$(date +"%A")
echo "Current Time: $CURRENT_TIME ($CURRENT_DAY)"

HOUR=$(date +"%H")
MINUTE=$(date +"%M")
TIME_NUM=$((10#$HOUR * 60 + 10#$MINUTE))

# Market hours: 9:15 AM (555) to 3:30 PM (930)
if [ $TIME_NUM -ge 555 ] && [ $TIME_NUM -le 930 ] && [ "$CURRENT_DAY" != "Saturday" ] && [ "$CURRENT_DAY" != "Sunday" ]; then
    echo -e "${GREEN}✅ MARKET IS OPEN${NC}"
else
    echo -e "${YELLOW}⚠️  MARKET IS CLOSED${NC}"
    echo "   (Live data not expected)"
fi
echo ""

# 11. SUMMARY
echo "════════════════════════════════════════════════════════════════"
echo "📋 DIAGNOSTIC SUMMARY"
echo "════════════════════════════════════════════════════════════════"

# Count issues
ISSUES=0

# Check databases
if [ ! -f "market_data.db" ] || [ -z "$(sqlite3 market_data.db '.tables' 2>/dev/null)" ]; then
    echo -e "${RED}❌ CRITICAL: market_data.db empty or missing${NC}"
    ISSUES=$((ISSUES + 1))
fi

if [ -f "alerts_pro.db" ]; then
    if ! sqlite3 alerts_pro.db "SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'" | grep -q "alerts"; then
        echo -e "${YELLOW}⚠️  WARNING: alerts table name mismatch${NC}"
        ISSUES=$((ISSUES + 1))
    fi
fi

# Check processes
for proc in "${PROCESSES[@]}"; do
    IFS=':' read -r pattern name <<< "$proc"
    if ! pgrep -f "$pattern" > /dev/null 2>&1; then
        ISSUES=$((ISSUES + 1))
    fi
done

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ All systems operational!${NC}"
else
    echo -e "${RED}❌ Found $ISSUES issues that need attention${NC}"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"

