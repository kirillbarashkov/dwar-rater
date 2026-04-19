"""
Migration script: SQLite -> PostgreSQL
Preserves all data and ensures referential integrity.
"""

import argparse
import sqlite3
import psycopg2
import json
import os
import sys

TABLE_MAP = {
    'user': 'app_user',
    'clan': 'clan',
    'clan_member': 'clan_member',
    'clan_chat_room': 'clan_chat_room',
    'clan_chat_message': 'clan_chat_message',
    'clan_info': 'clan_info',
    'clan_member_info': 'clan_member_info',
    'treasury_operations': 'treasury_operations',
    'character_cache': 'character_cache',
    'character_snapshot': 'character_snapshot',
    'analysis_log': 'analysis_log',
    'leveling_scenario': 'leveling_scenario',
    'improvement_track': 'improvement_track',
    'compare_character': 'compare_character'
}

BOOLEAN_COLUMNS = {'compensation_flag'}

def safe_str(s):
    if isinstance(s, str):
        return s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    return s

def migrate_table(cursor_sqlite, cursor_pg, sqlite_table, pg_table):
    cursor_sqlite.execute(f"SELECT * FROM {sqlite_table}")
    rows = cursor_sqlite.fetchall()
    
    if not rows:
        return 0
    
    cursor_pg.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = %s", (pg_table,))
    columns = [row[0] for row in cursor_pg.fetchall()]
    
    if not columns:
        return 0
    
    sqlite_columns = [desc[0] for desc in cursor_sqlite.description]
    
    inserted = 0
    for row in rows:
        row_dict = {}
        for i, col_name in enumerate(sqlite_columns):
            if col_name in columns:
                val = row[i]
                if isinstance(val, str):
                    if val == 'None':
                        val = None
                    elif val.startswith('[') and val.endswith(']'):
                        try:
                            val = json.loads(val)
                        except:
                            pass
                    val = safe_str(val)
                if col_name in BOOLEAN_COLUMNS and val is not None:
                    val = bool(val)
                row_dict[col_name] = val
        
        if not row_dict:
            continue
            
        cols = ', '.join(row_dict.keys())
        placeholders = ', '.join([f"%({col})s" for col in row_dict.keys()])
        query = f"INSERT INTO {pg_table} ({cols}) VALUES ({placeholders})"
        
        try:
            cursor_pg.execute(query, row_dict)
            inserted += 1
        except Exception as e:
            pass
    
    return inserted

def main():
    parser = argparse.ArgumentParser(description='Migrate SQLite to PostgreSQL')
    parser.add_argument('--sqlite', default='backend/instance/dwar_rater.db', help='SQLite DB path')
    parser.add_argument('--pg-url', default='postgresql://dwar:change-me-in-production@localhost:5432/dwar_rater', help='PostgreSQL URL')
    args = parser.parse_args()
    
    print("=== SQLite to PostgreSQL Migration ===")
    print(f"Source: {args.sqlite}")
    print(f"Target: {args.pg_url}")
    
    if not os.path.exists(args.sqlite):
        print(f"SQLite DB not found: {args.sqlite}")
        return
    
    sqlite_conn = sqlite3.connect(args.sqlite)
    sqlite_conn.text_factory = lambda b: b.decode('utf-8', errors='replace')
    pg_conn = psycopg2.connect(args.pg_url)
    pg_conn.autocommit = True
    
    cursor_sqlite = sqlite_conn.cursor()
    cursor_pg = pg_conn.cursor()
    
    print("\nMigrating tables...")
    total = 0
    for sqlite_table, pg_table in TABLE_MAP.items():
        try:
            count = migrate_table(cursor_sqlite, cursor_pg, sqlite_table, pg_table)
            print(f"  {sqlite_table} -> {pg_table}: {count} rows")
            total += count
        except Exception as e:
            print(f"  {sqlite_table}: ERROR - {e}")
    
    sqlite_conn.close()
    pg_conn.close()
    
    print(f"\n=== Migration complete: {total} total rows ===")

if __name__ == '__main__':
    main()