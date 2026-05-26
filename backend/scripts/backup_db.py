"""
Pre-migration backup script for Dwar Rater PostgreSQL database.

Usage:
    python backend/scripts/backup_db.py              # Full backup
    python backend/scripts/backup_db.py --list        # List existing backups
    python backend/scripts/backup_db.py --verify FILE # Verify a specific backup

Requires:
    - Docker container 'dwar_rater_postgres' running
    - pg_dump available inside the container (included in postgres image)

Backups are stored in:
    - Inside container: /backups/
    - Docker volume: dwar-rater_postgres_backups
    - Local copy: backup/ (project root)
"""
import os
import sys
import subprocess
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKUP_DIR = os.path.join(PROJECT_ROOT, 'backup')
CONTAINER_NAME = 'dwar_rater_postgres'
CONTAINER_BACKUP_DIR = '/backups'

DB_USER = os.environ.get('POSTGRES_USER', 'dwar')
DB_NAME = os.environ.get('POSTGRES_DB', 'dwar_rater')


def ensure_local_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def run_container_backup(filename):
    """Run pg_dump inside the PostgreSQL container and save to /backups volume."""
    filepath = f'{CONTAINER_BACKUP_DIR}/{filename}'

    cmd = [
        'docker', 'exec', CONTAINER_NAME,
        'pg_dump',
        '-U', DB_USER,
        '-d', DB_NAME,
        '-F', 'p',
        '--clean',
        '--if-exists',
        '--no-owner',
        '--no-acl',
    ]

    print(f'[{datetime.now().strftime("%H:%M:%S")}] Running pg_dump inside {CONTAINER_NAME}...')
    result = subprocess.run(cmd, capture_output=True, timeout=120)

    if result.returncode != 0:
        print(f'ERROR: pg_dump failed (exit code {result.returncode})')
        print(result.stderr.decode('utf-8', errors='replace'))
        return False

    content = result.stdout.decode('utf-8')
    container_path = filepath

    # Write to container volume via docker cp
    local_temp = os.path.join(BACKUP_DIR, filename)
    with open(local_temp, 'w', encoding='utf-8') as f:
        f.write(content)

    # Copy to container backup volume
    cp_cmd = ['docker', 'cp', local_temp, f'{CONTAINER_NAME}:{container_path}']
    cp_result = subprocess.run(cp_cmd, capture_output=True, timeout=30)
    if cp_result.returncode != 0:
        print(f'WARNING: Failed to copy backup to container volume: {cp_result.stderr.decode("utf-8", errors="replace")}')
        print(f'Backup saved locally: {local_temp}')
    else:
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Backup saved to container: {container_path}')
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Local copy: {local_temp}')

    return True


def verify_backup(filepath):
    """Verify backup file contains valid SQL structure."""
    if not os.path.exists(filepath):
        print(f'ERROR: File not found: {filepath}')
        return False

    size = os.path.getsize(filepath)
    print(f'File size: {size:,} bytes ({size / 1024:.1f} KB)')

    if size < 100:
        print('ERROR: File too small, likely empty')
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = {
        'CREATE TABLE': 'CREATE TABLE' in content,
        'INSERT INTO': 'INSERT INTO' in content or 'COPY' in content,
        'alembic_version': 'alembic_version' in content,
        'app_user': 'app_user' in content,
        'treasury_operations': 'treasury_operations' in content,
    }

    all_ok = True
    for name, passed in checks.items():
        status = 'OK' if passed else 'MISSING'
        if not passed:
            all_ok = False
        print(f'  [{status}] {name}')

    return all_ok


def list_backups():
    """List existing backups in container volume."""
    cmd = ['docker', 'exec', CONTAINER_NAME, 'ls', '-lh', CONTAINER_BACKUP_DIR]
    result = subprocess.run(cmd, capture_output=True, timeout=10)

    if result.returncode != 0:
        print(f'ERROR: {result.stderr.decode("utf-8", errors="replace")}')
        return

    lines = result.stdout.decode('utf-8').strip().split('\n')
    if len(lines) <= 1 or not lines[0].startswith('total'):
        print('No backups found in container volume.')
        return

    print(f'Backups in {CONTAINER_NAME}:{CONTAINER_BACKUP_DIR}/')
    print('-' * 60)
    for line in lines[1:]:
        if line.strip():
            print(f'  {line.strip()}')

    # Also list local backups
    if os.path.exists(BACKUP_DIR):
        local_files = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.sql')]
        if local_files:
            print(f'\nLocal backups in {BACKUP_DIR}/')
            print('-' * 60)
            for f in sorted(local_files):
                size = os.path.getsize(os.path.join(BACKUP_DIR, f))
                print(f'  {f} ({size:,} bytes)')


def main():
    ensure_local_backup_dir()

    if '--list' in sys.argv:
        list_backups()
        return

    if '--verify' in sys.argv:
        idx = sys.argv.index('--verify')
        if idx + 1 >= len(sys.argv):
            print('ERROR: --verify requires a filename argument')
            sys.exit(1)
        filepath = sys.argv[idx + 1]
        print(f'Verifying: {filepath}')
        if verify_backup(filepath):
            print('\nBackup is VALID.')
        else:
            print('\nBackup is INVALID or INCOMPLETE.')
            sys.exit(1)
        return

    # Full backup
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'pre-migration-{timestamp}.sql'

    print('=' * 60)
    print(f'Dwar Rater — Pre-Migration Backup')
    print(f'Timestamp: {timestamp}')
    print(f'Database:  {DB_NAME} (container: {CONTAINER_NAME})')
    print('=' * 60)

    # Check container is running
    check_cmd = ['docker', 'inspect', '-f', '{{.State.Running}}', CONTAINER_NAME]
    check_result = subprocess.run(check_cmd, capture_output=True, timeout=10)
    if check_result.stdout.decode().strip() != 'true':
        print(f'ERROR: Container {CONTAINER_NAME} is not running')
        sys.exit(1)

    success = run_container_backup(filename)

    if success:
        local_path = os.path.join(BACKUP_DIR, filename)
        print(f'\nVerifying backup...')
        if verify_backup(local_path):
            print(f'\nBackup completed successfully: {filename}')
        else:
            print(f'\nWARNING: Backup may be incomplete!')
            sys.exit(1)
    else:
        print('\nBackup FAILED.')
        sys.exit(1)


if __name__ == '__main__':
    main()
