#!/usr/bin/env python3
"""
TRADING SECRETS - TELEGRAM CONFIGURATION
==========================================
Instructions for setup:

1. Get Telegram Bot Token:
   - Open Telegram app
   - Search for @BotFather
   - Send /newbot command
   - Follow instructions to create bot
   - Copy the token you receive (format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)

2. Get Chat ID:
   - Start a chat with your bot
   - Send any message
   - Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   - Look for "chat":{"id": 123456789}
   - Copy that ID number

3. Update values below and save this file
"""

# =====================================================
# TELEGRAM CONFIGURATION
# =====================================================

# Your Telegram Bot Token from @BotFather
# Example format: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Your Telegram Chat ID (numeric)
# Example format: "123456789" or "-123456789" for groups
CHAT_ID = "YOUR_CHAT_ID_HERE"

# =====================================================
# VALIDATION
# =====================================================

def validate_config():
    """Check if configuration is valid"""
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE" or CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("⚠️  WARNING: Telegram credentials not configured!")
        print("⚠️  Edit trading_secrets.py with your Bot Token and Chat ID")
        print("⚠️  Alerts will be logged but NOT sent to Telegram")
        return False
    return True

if __name__ == "__main__":
    if validate_config():
        print("✅ Telegram configuration is valid")
        print(f"✅ Bot Token: {TELEGRAM_TOKEN[:10]}...")
        print(f"✅ Chat ID: {CHAT_ID}")
    else:
        print("❌ Configuration incomplete")
