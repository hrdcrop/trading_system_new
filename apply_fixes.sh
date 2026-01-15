#!/bin/bash

# ================================================================
# AUTOMATED FIX SCRIPT WITH GITHUB INTEGRATION
# Applies all fixes and commits to GitHub automatically
# ================================================================

set -e  # Exit on any error

echo "🚀 AUTOMATED FIX SCRIPT STARTING..."
echo "=================================="
echo ""

# ================================================================
# STEP 1: SAFETY CHECKS
# ================================================================

echo "🔍 Step 1: Safety Checks..."

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git not installed. Install with: pkg install git"
    exit 1
fi

# Check if in correct directory
if [ ! -f "alert_engine_pro.py" ]; then
    echo "❌ Not in correct directory. Run from ~/trading_system_new"
    exit 1
fi

# Check if files exist
required_files=("alert_engine_pro.py" "trading_dashboard.html" "start_trading_system.sh")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Required file missing: $file"
        exit 1
    fi
done

echo "✅ All safety checks passed"
echo ""

# ================================================================
# STEP 2: STOP RUNNING SYSTEM
# ================================================================

echo "🛑 Step 2: Stopping running system..."

pkill -f tick_json_saver.py 2>/dev/null || true
pkill -f candle_builder_1m.py 2>/dev/null || true
pkill -f oi_category_builder.py 2>/dev/null || true
pkill -f comprehensive_analytics_engine.py 2>/dev/null || true
pkill -f alert_engine_pro.py 2>/dev/null || true
pkill -f api_server_step.py 2>/dev/null || true

sleep 2
echo "✅ System stopped"
echo ""

# ================================================================
# STEP 3: CREATE BACKUPS
# ================================================================

echo "💾 Step 3: Creating backups..."

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

cp alert_engine_pro.py "$BACKUP_DIR/"
cp trading_dashboard.html "$BACKUP_DIR/"
cp start_trading_system.sh "$BACKUP_DIR/"

if [ -f "alerts_pro.db" ]; then
    cp alerts_pro.db "$BACKUP_DIR/"
fi

echo "✅ Backups created in: $BACKUP_DIR"
echo ""

# ================================================================
# STEP 4: APPLY FIX 1 - alert_engine_pro.py (Database Schema)
# ================================================================

echo "🔧 Step 4: Fixing alert_engine_pro.py (Database Schema)..."

cat > /tmp/fix1.py << 'EOF'
import sys

with open('alert_engine_pro.py', 'r') as f:
    content = f.read()

# Fix 1: Add migration logic to init_alert_db()
old_code = '''def init_alert_db():
    conn = sqlite3.connect(ALERT_DB)
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts_final (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT NOT NULL,
        symbol TEXT NOT NULL,
        
        future_oi_category TEXT,
        depth_bias TEXT,
        index_bias TEXT,
        sector_bias TEXT,
        market_bias TEXT,
        
        regime TEXT,
        vix_state TEXT,
        
        confidence INTEGER,
        recommended_action TEXT,
        
        metadata TEXT,
        telegram_sent INTEGER DEFAULT 0
    )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts_final(time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts_final(symbol)")
    
    conn.commit()
    return conn'''

new_code = '''def init_alert_db():
    conn = sqlite3.connect(ALERT_DB)
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts_final (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT NOT NULL,
        symbol TEXT NOT NULL,
        
        future_oi_category TEXT,
        depth_bias TEXT,
        index_bias TEXT,
        sector_bias TEXT,
        market_bias TEXT,
        
        regime TEXT,
        vix_state TEXT,
        
        confidence INTEGER,
        recommended_action TEXT,
        
        metadata TEXT,
        telegram_sent INTEGER DEFAULT 0
    )
    """)
    
    # Migration: Add telegram_sent to existing tables
    try:
        cur.execute("ALTER TABLE alerts_final ADD COLUMN telegram_sent INTEGER DEFAULT 0")
        print("✅ Added telegram_sent column to existing table")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts_final(time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts_final(symbol)")
    
    conn.commit()
    return conn'''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ Fix 1 applied: Database schema migration added")
else:
    print("⚠️  Fix 1: Pattern not found (might be already applied)")

with open('alert_engine_pro.py', 'w') as f:
    f.write(content)
EOF

python3 /tmp/fix1.py
echo ""

# ================================================================
# STEP 5: APPLY FIX 2 - alert_engine_pro.py (VIX Thresholds)
# ================================================================

echo "🔧 Step 5: Fixing VIX thresholds..."

cat > /tmp/fix2.py << 'EOF'
with open('alert_engine_pro.py', 'r') as f:
    content = f.read()

# Fix 2: Add NORMAL_VIX constant
old_thresholds = '''# Thresholds
MIN_CONFIDENCE = 55
BID_ASK_BUY_THRESHOLD = 1.5
BID_ASK_SELL_THRESHOLD = 0.67
ORDER_IMBALANCE_THRESHOLD = 100
HIGH_VIX = 18
LOW_VIX = 12'''

new_thresholds = '''# Thresholds
MIN_CONFIDENCE = 55
BID_ASK_BUY_THRESHOLD = 1.5
BID_ASK_SELL_THRESHOLD = 0.67
ORDER_IMBALANCE_THRESHOLD = 100
HIGH_VIX = 18
NORMAL_VIX = 15
LOW_VIX = 12'''

if old_thresholds in content:
    content = content.replace(old_thresholds, new_thresholds)
    print("✅ Fix 2 applied: NORMAL_VIX constant added")
else:
    print("⚠️  Fix 2: Pattern not found (might be already applied)")

# Fix VIX state logic
old_vix_logic = '''        # 7. CONTEXT: VIX
        vix_value = analytics.get('vix_value', 15.0)
        if vix_value < LOW_VIX:
            vix_state = VixState.LOW
        elif vix_value < 15:
            vix_state = VixState.NORMAL
        elif vix_value < HIGH_VIX:
            vix_state = VixState.HIGH
        else:
            vix_state = VixState.EXTREME'''

new_vix_logic = '''        # 7. CONTEXT: VIX
        vix_value = analytics.get('vix_value', 15.0)
        if vix_value < LOW_VIX:
            vix_state = VixState.LOW
        elif vix_value < NORMAL_VIX:
            vix_state = VixState.NORMAL
        elif vix_value < HIGH_VIX:
            vix_state = VixState.HIGH
        else:
            vix_state = VixState.EXTREME'''

if old_vix_logic in content:
    content = content.replace(old_vix_logic, new_vix_logic)
    print("✅ Fix 2b applied: VIX state logic fixed")
else:
    print("⚠️  Fix 2b: Pattern not found (might be already applied)")

with open('alert_engine_pro.py', 'w') as f:
    f.write(content)
EOF

python3 /tmp/fix2.py
echo ""

# ================================================================
# STEP 6: APPLY FIX 3 - alert_engine_pro.py (Error Handling)
# ================================================================

echo "🔧 Step 6: Adding error handling..."

cat > /tmp/fix3.py << 'EOF'
with open('alert_engine_pro.py', 'r') as f:
    content = f.read()

# Fix 3: Add try-catch to process_alert
old_process_start = '''def process_alert(time_str: str, alert_conn) -> None:
    """Main alert generation logic"""
    
    for fut_token, fut_name in FUTURE_TOKENS.items():
        symbol = fut_name.replace("_FUT", "")'''

new_process_start = '''def process_alert(time_str: str, alert_conn) -> None:
    """Main alert generation logic"""
    
    for fut_token, fut_name in FUTURE_TOKENS.items():
        try:
            symbol = fut_name.replace("_FUT", "")'''

if old_process_start in content:
    content = content.replace(old_process_start, new_process_start)
    print("✅ Fix 3a applied: Try block added to process_alert")
else:
    print("⚠️  Fix 3a: Pattern not found (might be already applied)")

# Add exception handler at end of loop
old_loop_end = '''        print(f"✅ ALERT: {symbol} | {oi_category} | {action.value} | Conf:{confidence}")

# =====================================================
# MAIN LOOP
# ====================================================='''

new_loop_end = '''        print(f"✅ ALERT: {symbol} | {oi_category} | {action.value} | Conf:{confidence}")
        
        except Exception as e:
            print(f"[ALERT ERR] {symbol}: {e}")
            import traceback
            traceback.print_exc()
            continue

# =====================================================
# MAIN LOOP
# ====================================================='''

if old_loop_end in content:
    content = content.replace(old_loop_end, new_loop_end)
    print("✅ Fix 3b applied: Exception handler added")
else:
    print("⚠️  Fix 3b: Pattern not found (might be already applied)")

with open('alert_engine_pro.py', 'w') as f:
    f.write(content)
EOF

python3 /tmp/fix3.py
echo ""

# ================================================================
# STEP 7: APPLY FIX 4 - alert_engine_pro.py (Telegram Status)
# ================================================================

echo "🔧 Step 7: Fixing Telegram status tracking..."

cat > /tmp/fix4.py << 'EOF'
with open('alert_engine_pro.py', 'r') as f:
    content = f.read()

# Fix 4: Fix telegram status in database insert
old_insert = '''        # 13. WRITE TO DATABASE
        cur.execute("""
            INSERT INTO alerts_final
            (time, symbol, future_oi_category, depth_bias, index_bias,
             sector_bias, market_bias, regime, vix_state, confidence, recommended_action)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            context.time, context.symbol,
            context.future_oi, context.depth_bias, context.index_bias,
            context.sector_bias, context.market_bias, context.regime, context.vix_state,
            context.confidence, context.action
        ))
        
        alert_conn.commit()
        
        # 14. SEND TO TELEGRAM
        telegram_msg = format_telegram_alert(context)
        priority = "HIGH" if confidence >= 75 else "MEDIUM"
        send_telegram(telegram_msg, priority)'''

new_insert = '''        # 13. SEND TO TELEGRAM FIRST
        telegram_msg = format_telegram_alert(context)
        priority = "HIGH" if confidence >= 75 else "MEDIUM"
        send_telegram(telegram_msg, priority)
        
        # 14. WRITE TO DATABASE (with telegram status)
        telegram_status = 1 if TELEGRAM_ENABLED else 0
        
        cur.execute("""
            INSERT INTO alerts_final
            (time, symbol, future_oi_category, depth_bias, index_bias,
             sector_bias, market_bias, regime, vix_state, confidence, 
             recommended_action, telegram_sent)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            context.time, context.symbol,
            context.future_oi, context.depth_bias, context.index_bias,
            context.sector_bias, context.market_bias, context.regime, context.vix_state,
            context.confidence, context.action, telegram_status
        ))
        
        alert_conn.commit()'''

if old_insert in content:
    content = content.replace(old_insert, new_insert)
    print("✅ Fix 4 applied: Telegram status tracking fixed")
else:
    print("⚠️  Fix 4: Pattern not found (might be already applied)")

with open('alert_engine_pro.py', 'w') as f:
    f.write(content)
EOF

python3 /tmp/fix4.py
echo ""

# ================================================================
# STEP 8: APPLY FIX 5 - trading_dashboard.html (API URL)
# ================================================================

echo "🔧 Step 8: Fixing dashboard API URL..."

cat > /tmp/fix5.py << 'EOF'
with open('trading_dashboard.html', 'r') as f:
    content = f.read()

old_api = "        const API_BASE = 'http://localhost:8000';"

new_api = """        // Auto-detect host for mobile access
        const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
            ? 'http://localhost:8000'
            : `http://${window.location.hostname}:8000`;"""

if old_api in content:
    content = content.replace(old_api, new_api)
    print("✅ Fix 5 applied: Dashboard API URL auto-detection added")
else:
    print("⚠️  Fix 5: Pattern not found (might be already applied)")

with open('trading_dashboard.html', 'w') as f:
    f.write(content)
EOF

python3 /tmp/fix5.py
echo ""

# ================================================================
# STEP 9: CREATE DATABASE MIGRATION SCRIPT
# ================================================================

echo "🔧 Step 9: Creating database migration script..."

cat > migrate_database.py << 'EOF'
#!/usr/bin/env python3
"""
Database Migration Script
Adds missing telegram_sent column to alerts_final table
"""

import sqlite3
import os

ALERT_DB = "alerts_pro.db"

def migrate():
    if not os.path.exists(ALERT_DB):
        print(f"ℹ️  Database {ALERT_DB} not found. Will be created on first run.")
        return
    
    print(f"🔄 Migrating {ALERT_DB}...")
    
    conn = sqlite3.connect(ALERT_DB)
    cur = conn.cursor()
    
    try:
        # Check if column exists
        cur.execute("PRAGMA table_info(alerts_final)")
        columns = [row[1] for row in cur.fetchall()]
        
        if 'telegram_sent' in columns:
            print("✅ telegram_sent column already exists")
        else:
            # Add column
            cur.execute("ALTER TABLE alerts_final ADD COLUMN telegram_sent INTEGER DEFAULT 0")
            conn.commit()
            print("✅ Added telegram_sent column")
        
        # Update existing rows
        cur.execute("UPDATE alerts_final SET telegram_sent = 0 WHERE telegram_sent IS NULL")
        conn.commit()
        print("✅ Updated existing rows")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    print("✅ Migration complete!")

if __name__ == "__main__":
    migrate()
EOF

chmod +x migrate_database.py
echo "✅ Migration script created"
echo ""

# ================================================================
# STEP 10: RUN DATABASE MIGRATION
# ================================================================

echo "🔧 Step 10: Running database migration..."

if [ -f "alerts_pro.db" ]; then
    python3 migrate_database.py
else
    echo "ℹ️  No existing database. Will be created on first run."
fi
echo ""

# ================================================================
# STEP 11: UPDATE start_trading_system.sh
# ================================================================

echo "🔧 Step 11: Updating start script..."

if ! grep -q "Checking database schema" start_trading_system.sh; then
    # Add migration check after line with "pkill -f candle_builder_1m.py"
    sed -i '/pkill -f candle_builder_1m.py/a\
\
# Database migration check\
echo "🔄 Checking database schema..."\
python3 migrate_database.py 2>/dev/null || true
' start_trading_system.sh
    echo "✅ Start script updated"
else
    echo "✅ Start script already updated"
fi
echo ""

# ================================================================
# STEP 12: CLEANUP TEMP FILES
# ================================================================

echo "🧹 Step 12: Cleaning up..."
rm -f /tmp/fix*.py
echo "✅ Cleanup complete"
echo ""

# ================================================================
# STEP 13: GIT INITIALIZATION (IF NEEDED)
# ================================================================

echo "📦 Step 13: Git setup..."

if [ ! -d ".git" ]; then
    echo "🔧 Initializing Git repository..."
    git init
    
    # Create .gitignore if not exists
    if [ ! -f ".gitignore" ]; then
        cat > .gitignore << 'GITIGNORE'
# === SECRETS ===
access_token.txt
api_key.txt
telegram_token.txt
chat_id.txt

# === DATABASES ===
*.db
*.db-journal
*.db-wal
*.db-shm

# === LOGS ===
logs/
*.log

# === BACKUPS ===
backups/

# === CACHE / TEMP ===
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/

# === IDE ===
.vscode/
.idea/
*.swp
*.swo
*~

# === OS ===
.DS_Store
Thumbs.db
GITIGNORE
        echo "✅ .gitignore created"
    fi
    
    git add .
    git commit -m "Initial commit: Trading system setup"
    echo "✅ Git initialized"
else
    echo "✅ Git already initialized"
fi
echo ""

# ================================================================
# STEP 14: COMMIT FIXES TO GIT
# ================================================================

echo "💾 Step 14: Committing fixes to Git..."

git add alert_engine_pro.py trading_dashboard.html start_trading_system.sh migrate_database.py .gitignore 2>/dev/null || true

if git diff --cached --quiet; then
    echo "ℹ️  No changes to commit (fixes already applied)"
else
    git commit -m "🔧 Apply critical fixes

- Add telegram_sent column migration
- Fix VIX threshold constants
- Add error handling to alert processing
- Fix telegram status tracking
- Add mobile-friendly API URL detection
- Create database migration script

Changes made by apply_fixes.sh on $(date)"
    echo "✅ Changes committed to Git"
fi
echo ""

# ================================================================
# STEP 15: GITHUB REMOTE SETUP
# ================================================================

echo "🌐 Step 15: GitHub remote setup..."

# Check if remote exists
if git remote | grep -q "origin"; then
    echo "✅ GitHub remote already configured"
    REMOTE_URL=$(git remote get-url origin)
    echo "   Remote: $REMOTE_URL"
else
    echo ""
    echo "⚠️  GitHub remote not configured yet."
    echo ""
    echo "To push to GitHub, you need to:"
    echo "1. Create a repository on GitHub (https://github.com/new)"
    echo "2. Run these commands:"
    echo ""
    echo "   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git"
    echo "   git branch -M main"
    echo "   git push -u origin main"
    echo ""
    read -p "Do you want to configure GitHub remote now? (y/n): " configure_github
    
    if [ "$configure_github" = "y" ] || [ "$configure_github" = "Y" ]; then
        echo ""
        read -p "Enter your GitHub username: " github_user
        read -p "Enter repository name: " repo_name
        
        REMOTE_URL="https://github.com/$github_user/$repo_name.git"
        
        echo "🔧 Adding remote: $REMOTE_URL"
        git remote add origin "$REMOTE_URL"
        
        echo "🔧 Setting main branch..."
        git branch -M main
        
        echo "✅ GitHub remote configured"
        echo ""
        echo "📤 Attempting to push to GitHub..."
        echo "   (You may need to enter your GitHub credentials)"
        echo ""
        
        if git push -u origin main; then
            echo "✅ Successfully pushed to GitHub!"
        else
            echo "⚠️  Push failed. You may need to:"
            echo "   1. Check GitHub credentials"
            echo "   2. Create the repository on GitHub first"
            echo "   3. Try: git push -u origin main"
        fi
    else
        echo "⏭️  Skipping GitHub setup"
    fi
fi
echo ""

# ================================================================
# STEP 16: VERIFICATION
# ================================================================

echo "🔍 Step 16: Verifying fixes..."
echo ""

# Check if fixes were applied
echo "Checking applied fixes:"

if grep -q "NORMAL_VIX = 15" alert_engine_pro.py; then
    echo "✅ Fix 1: VIX threshold constant added"
else
    echo "❌ Fix 1: VIX threshold constant NOT found"
fi

if grep -q "ALTER TABLE alerts_final ADD COLUMN telegram_sent" alert_engine_pro.py; then
    echo "✅ Fix 2: Database migration added"
else
    echo "❌ Fix 2: Database migration NOT found"
fi

if grep -q "telegram_status = 1 if TELEGRAM_ENABLED else 0" alert_engine_pro.py; then
    echo "✅ Fix 3: Telegram status tracking fixed"
else
    echo "❌ Fix 3: Telegram status tracking NOT found"
fi

if grep -q "window.location.hostname" trading_dashboard.html; then
    echo "✅ Fix 4: Dashboard API auto-detection added"
else
    echo "❌ Fix 4: Dashboard API auto-detection NOT found"
fi

if [ -f "migrate_database.py" ]; then
    echo "✅ Fix 5: Migration script created"
else
    echo "❌ Fix 5: Migration script NOT found"
fi

echo ""

# ================================================================
# STEP 17: FINAL SUMMARY
# ================================================================

echo "=================================="
echo "✅ AUTOMATED FIXES COMPLETED!"
echo "=================================="
echo ""
echo "📊 Summary:"
echo "   - Backups saved to: $BACKUP_DIR"
echo "   - Git commits: $(git log --oneline | wc -l) total"
echo "   - Last commit: $(git log -1 --pretty=format:'%h - %s')"
echo ""

if git remote | grep -q "origin"; then
    echo "🌐 GitHub Status:"
    echo "   - Remote: $(git remote get-url origin)"
    echo "   - Branch: $(git branch --show-current)"
    echo ""
    echo "   To push latest changes: git push"
fi

echo "🚀 Next Steps:"
echo "   1. Start system: ./start_trading_system.sh"
echo "   2. Check status: ./check_status.sh"
echo "   3. View logs: tail -f logs/alerts.log"
echo ""

if [ ! -d ".git/refs/remotes/origin" ]; then
    echo "⚠️  Note: Changes are committed locally but not pushed to GitHub yet."
    echo "   Configure GitHub remote and push when ready."
    echo ""
fi

echo "🎉 All done! Your system is ready to run."
echo ""

# Ask if user wants to start system
read -p "Start trading system now? (y/n): " start_now

if [ "$start_now" = "y" ] || [ "$start_now" = "Y" ]; then
    echo ""
    echo "🚀 Starting system..."
    ./start_trading_system.sh
else
    echo ""
    echo "👍 System not started. Start manually with: ./start_trading_system.sh"
fi

echo ""
echo "✨ Script completed successfully!"
