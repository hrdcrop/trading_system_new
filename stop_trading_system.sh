#!/bin/bash

echo "🛑 Stopping Trading System..."

pkill -f tick_json_saver.py
pkill -f candle_builder_1m.py
pkill -f oi_category_builder.py
pkill -f comprehensive_analytics_engine.py
pkill -f alert_engine_pro.py
pkill -f api_server_step.py

sleep 2

echo "✅ All processes stopped"
