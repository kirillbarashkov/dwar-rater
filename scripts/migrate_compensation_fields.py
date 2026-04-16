"""
Migration script to add compensation fields to treasury_operations table.
Run this script once to update existing databases with the new compensation columns.

Usage:
    python scripts/migrate_compensation_fields.py
"""

import sqlite3
import os
import sys

def migrate(db_path):
    """Add compensation_flag and compensation_comment columns if they don't exist."""
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(treasury_operations)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'compensation_flag' not in columns:
        print("Adding compensation_flag column...")
        cursor.execute("ALTER TABLE treasury_operations ADD COLUMN compensation_flag BOOLEAN DEFAULT 0")
        print("  - compensation_flag column added")
    else:
        print("compensation_flag column already exists")
    
    if 'compensation_comment' not in columns:
        print("Adding compensation_comment column...")
        cursor.execute("ALTER TABLE treasury_operations ADD COLUMN compensation_comment TEXT DEFAULT ''")
        print("  - compensation_comment column added")
    else:
        print("compensation_comment column already exists")
    
    conn.commit()
    conn.close()
    
    print("Migration completed successfully!")

if __name__ == '__main__':
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', 'instance', 'dwar_rater.db')
    migrate(db_path)
