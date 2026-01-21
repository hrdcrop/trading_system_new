#!/bin/bash

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          ✅ SYSTEM VERIFICATION                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 1. Check all databases
echo "📊 DATABASE STATUS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sqlite3 tick_json_data.db "SELECT COUNT(*) || ' ticks' FROM ticks_json"
sqlite3 market_data.db "SELECT COUNT(*) || ' candles' FROM minute_candles"
sqlite3 market_analytics.db "SELECT COUNT(*) || ' analytics rows' FROM minute_analytics"
sqlite3 alerts_pro.db "SELECT COUNT(*) || ' alerts' FROM alerts_final"
echo ""

# 2. Check latest data
echo "📈 LATEST DATA (BANKNIFTY):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sqlite3 market_data.db "SELECT time_minute, symbol, open, high, low, close FROM minute_candles WHERE symbol='BANKNIFTY' ORDER BY time_minute DESC LIMIT 3"
echo ""

# 3. Test API endpoints
echo "🌐 API ENDPOINTS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Market Latest:"
curl -s http://localhost:8000/market/latest | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  ✓ {len(d)} symbols returned\")" 2>/dev/null || echo "  ✗ Failed"

echo "Analytics Latest:"
curl -s http://localhost:8000/analytics/latest | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  ✓ {len(d)} analytics returned\")" 2>/dev/null || echo "  ✗ Failed"

echo "Alerts Latest:"
curl -s http://localhost:8000/alerts/latest | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  ✓ {len(d)} alerts returned\")" 2>/dev/null || echo "  ✗ Failed"
echo ""

# 4. Check dashboard
echo "🎨 DASHBOARD TEST:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DASHBOARD_SIZE=$(curl -s http://localhost:8000/ | wc -c)
if [ "$DASHBOARD_SIZE" -gt 10000 ]; then
    echo "  ✓ Dashboard HTML loaded ($DASHBOARD_SIZE bytes)"
else
    echo "  ✗ Dashboard issue (only $DASHBOARD_SIZE bytes)"
fi
echo ""

# 5. Recent alerts
echo "🚨 RECENT ALERTS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sqlite3 alerts_pro.db "SELECT time, symbol, recommended_action, confidence FROM alerts_final ORDER BY id DESC LIMIT 5"
echo ""

# 6. Alert engine status
echo "📱 ALERT ENGINE STATUS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if pgrep -f "alert_engine_pro.py" > /dev/null; then
    echo "  ✓ Alert engine is running"
    tail -5 logs/alert_engine.log | grep -E "(PROCESSING|Alert generated|Telegram)" || echo "  No recent activity"
else
    echo "  ✗ Alert engine NOT running"
fi
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  🎯 NEXT STEPS                             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "1. Open Dashboard: http://localhost:8000"
echo "2. Check Telegram for alerts"
echo "3. Monitor logs:"
echo "   tail -f logs/alert_engine.log"
echo "   tail -f logs/analytics_engine.log"
echo ""
echo "4. If alerts not showing on dashboard:"
echo "   - Press Ctrl+Shift+R to hard refresh browser"
echo "   - Check browser console (F12) for errors"
echo ""
