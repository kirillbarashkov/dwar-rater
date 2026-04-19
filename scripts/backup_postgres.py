"""
PostgreSQL backup script.
Creates timestamped dumps and manages retention policy.

Usage:
    python scripts/backup_postgres.py                    # Default: local backup
    python scripts/backup_postgres.py --keep 7           # Keep 7 days
    python scripts/backup_postgres.py --cloud rclone      # Upload to cloud via rclone
"""

import os
import subprocess
import argparse
from datetime import datetime

BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'dwar_rater')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'dwar')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'change-me-in-production')

def create_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'dwar_rater_backup_{timestamp}.sql'
    filepath = os.path.join(BACKUP_DIR, filename)
    
    env = os.environ.copy()
    env['PGPASSWORD'] = POSTGRES_PASSWORD
    
    cmd = [
        'pg_dump',
        '-h', POSTGRES_HOST,
        '-p', POSTGRES_PORT,
        '-U', POSTGRES_USER,
        '-d', POSTGRES_DB,
        '-f', filepath,
        '--no-owner', '--no-acl'
    ]
    
    print(f"Creating backup: {filename}")
    result = subprocess.run(cmd, env=env)
    
    if result.returncode == 0:
        size = os.path.getsize(filepath) / 1024 / 1024
        print(f"Backup created: {size:.2f} MB")
        return filepath
    else:
        print(f"Backup failed: {result.stderr}")
        return None

def cleanup_old_backups(keep_days=7):
    if not os.path.exists(BACKUP_DIR):
        return
    
    cutoff = datetime.now().timestamp() - (keep_days * 86400)
    removed = 0
    
    for f in os.listdir(BACKUP_DIR):
        if f.startswith('dwar_rater_backup_') and f.endswith('.sql'):
            filepath = os.path.join(BACKUP_DIR, f)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                removed += 1
    
    if removed:
        print(f"Removed {removed} old backups")

def upload_to_cloud(backup_path):
    if not os.path.exists('.rclone.conf'):
        print("rclone config not found, skipping cloud upload")
        return False
    
    cloud_destination = os.environ.get('RCLONE_DESTINATION', 'gdrive:/dwar-rater-backups')
    
    print(f"Uploading to cloud: {cloud_destination}")
    result = subprocess.run([
        'rclone', 'copy', backup_path, cloud_destination,
        '--progress', '--transfers', '1'
    ])
    
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keep', type=int, default=7, help='Days to keep backups')
    parser.add_argument('--cloud', choices=['rclone'], help='Upload to cloud')
    args = parser.parse_args()
    
    print("=== PostgreSQL Backup ===")
    print(f"Time: {datetime.now().isoformat()}")
    
    backup_path = create_backup()
    if not backup_path:
        return
    
    cleanup_old_backups(args.keep)
    
    if args.cloud == 'rclone':
        upload_to_cloud(backup_path)
    
    print("=== Backup Complete ===")

if __name__ == '__main__':
    main()