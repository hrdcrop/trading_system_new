🚀 TRADING SYSTEM - QUICK START GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 DIRECTORY: ~/trading_system_new

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 SETUP (First Time Only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Edit credentials:
   nano api_key.txt          # Your Kite API key
   nano access_token.txt     # Your access token
   nano telegram_token.txt   # Your Telegram bot token
   nano chat_id.txt          # Your Telegram chat ID

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 START SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

./start_trading_system.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 STOP SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

./stop_trading_system.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 CHECK STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

./check_status.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 ACCESS DASHBOARD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open browser: http://localhost:8000

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 VIEW LOGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

tail -f logs/alerts.log       # Live alerts
tail -f logs/tick_capture.log # Tick capture
tail -f logs/analytics.log    # Analytics

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Check if programs running:
   ps aux | grep python

2. Check logs for errors:
   ls -lh logs/

3. Restart specific component:
   pkill -f tick_json_saver.py
   python3 tick_json_saver.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 FILES IN THIS DIRECTORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Config Files:
- api_key.txt
- access_token.txt
- telegram_token.txt
- chat_id.txt

Python Programs:
- tick_json_saver.py
- candle_builder_1m.py
- oi_category_builder.py
- comprehensive_analytics_engine.py
- alert_engine_pro.py
- api_server_step.py

Scripts:
- start_trading_system.sh
- stop_trading_system.sh
- check_status.sh

Dashboard:
- trading_dashboard.html

Logs:
- logs/ (directory)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ SYSTEM READY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
