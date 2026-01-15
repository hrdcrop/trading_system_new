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
