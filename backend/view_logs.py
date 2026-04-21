#!/usr/bin/env python3
"""View data operation logs."""
import os
import sys
from datetime import datetime

LOG_DIR = 'logs'

def tail_log(filepath, lines=50):
    """Print last lines of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.readlines()
            for line in content[-lines:]:
                print(line.rstrip())
    except FileNotFoundError:
        print(f"Log file not found: {filepath}")
    except Exception as e:
        print(f"Error reading log: {e}")

def list_logs():
    """List available log files."""
    if not os.path.exists(LOG_DIR):
        print(f"Log directory '{LOG_DIR}' not found.")
        return
    
    files = [f for f in os.listdir(LOG_DIR) if f.endswith('.log')]
    if not files:
        print("No log files found.")
        return
    
    print("Available log files:")
    for f in sorted(files, reverse=True):
        filepath = os.path.join(LOG_DIR, f)
        size = os.path.getsize(filepath)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        print(f"  {f} ({size/1024:.1f} KB, {mtime.strftime('%Y-%m-%d %H:%M')})")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            list_logs()
        elif sys.argv[1] == '--lines' and len(sys.argv) > 2:
            try:
                lines = int(sys.argv[2])
                today = f"data_operations_{datetime.now().strftime('%Y%m%d')}.log"
                filepath = os.path.join(LOG_DIR, today)
                tail_log(filepath, lines)
            except ValueError:
                print("Invalid number of lines")
        else:
            filepath = os.path.join(LOG_DIR, sys.argv[1])
            tail_log(filepath)
    else:
        today = f"data_operations_{datetime.now().strftime('%Y%m%d')}.log"
        filepath = os.path.join(LOG_DIR, today)
        print(f"=== Today's log: {today} ===\n")
        tail_log(filepath, 100)

if __name__ == '__main__':
    main()
