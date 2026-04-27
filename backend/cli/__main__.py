"""Dwar Rater CLI — management commands for the backend.

Usage:
    python -m cli users list --format json
    python -m cli users create --username test --role user --password secret
    python -m cli cache clear [--nick Nickname]
    python -m cli db status
    python -m cli db backup --output ./dump.json
    python -m cli health
    python -m cli analyze --url "https://w1.dwar.ru/user_info.php?nick=Test" --dry-run
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('AUTH_ENABLED', 'false')
os.environ.setdefault('ADMIN_USER', 'admin')
os.environ.setdefault('ADMIN_PASS', 'admin')
os.environ.setdefault('SECRET_KEY', 'cli-key')
os.environ.setdefault('CORS_ORIGINS', '*')
os.environ['CLI_MODE'] = 'true'

from app import create_app
from models import db
from models.user import User
from models.character_cache import CharacterCache
from models.clan_info import ClanInfo, ClanMemberInfo
from models.character_snapshot import CharacterSnapshot
from sqlalchemy import text


def _get_app():
    from config import Config
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('sqlite:///:memory'):
        Config.DATABASE_URL = 'sqlite:///instance/dwar_rater.db'
        os.environ['DATABASE_URL'] = Config.DATABASE_URL
    app = create_app()
    app.config['TESTING'] = True
    return app


def _output(data, fmt='table'):
    if fmt == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    for k, v in item.items():
                        print(f"  {k}: {v}")
                    print()
                else:
                    print(f"  {item}")
        elif isinstance(data, dict):
            for k, v in data.items():
                print(f"  {k}: {v}")
        else:
            print(data)


# ── users ──────────────────────────────────────────────────────────

def cmd_users_list(args):
    app = _get_app()
    with app.app_context():
        users = User.query.all()
        data = [
            {
                'id': u.id,
                'username': u.username,
                'role': u.role,
                'created_at': u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    _output(data, args.format)


def cmd_users_create(args):
    import bcrypt
    app = _get_app()
    with app.app_context():
        existing = User.query.filter_by(username=args.username).first()
        if existing:
            print(f"Error: user '{args.username}' already exists", file=sys.stderr)
            sys.exit(1)
        user = User(
            username=args.username,
            password_hash=bcrypt.hashpw(args.password.encode(), bcrypt.gensalt()).decode('utf-8'),
            role=args.role,
        )
        db.session.add(user)
        db.session.commit()
        _output({'status': 'created', 'id': user.id, 'username': user.username, 'role': user.role}, args.format)


def cmd_users_delete(args):
    app = _get_app()
    with app.app_context():
        user = User.query.filter_by(username=args.username).first()
        if not user:
            print(f"Error: user '{args.username}' not found", file=sys.stderr)
            sys.exit(1)
        db.session.delete(user)
        db.session.commit()
        _output({'status': 'deleted', 'username': args.username}, args.format)


# ── cache ──────────────────────────────────────────────────────────

def cmd_cache_clear(args):
    app = _get_app()
    with app.app_context():
        if args.nick:
            cache = CharacterCache.query.filter_by(nick=args.nick).first()
            if cache:
                db.session.delete(cache)
                db.session.commit()
                _output({'status': 'cleared', 'nick': args.nick}, args.format)
            else:
                print(f"Cache for '{args.nick}' not found", file=sys.stderr)
                sys.exit(1)
        else:
            count = CharacterCache.query.count()
            CharacterCache.query.delete()
            db.session.commit()
            _output({'status': 'cleared', 'entries_deleted': count}, args.format)


def cmd_cache_list(args):
    app = _get_app()
    with app.app_context():
        caches = CharacterCache.query.order_by(CharacterCache.updated_at.desc()).all()
        data = [
            {
                'nick': c.nick,
                'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                'data_size': len(c.raw_data),
            }
            for c in caches
        ]
    _output(data, args.format)


# ── db ─────────────────────────────────────────────────────────────

def cmd_db_status(args):
    app = _get_app()
    with app.app_context():
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        stats = {}
        for table in sorted(tables):
            if table == 'alembic_version':
                continue
            count = db.session.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
            stats[table] = count

        data = {
            'tables': len(tables),
            'table_counts': stats,
            'database_url': os.environ.get('DATABASE_URL', 'unknown'),
        }
    _output(data, args.format)


def cmd_db_backup(args):
    app = _get_app()
    with app.app_context():
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        tables = [t for t in inspector.get_table_names() if t != 'alembic_version']
        backup = {
            'version': 1,
            'backup_at': datetime.now(timezone.utc).isoformat(),
            'tables': {},
        }
        for table in tables:
            rows = db.session.execute(text(f'SELECT * FROM {table}')).mappings().all()
            backup['tables'][table] = [dict(r) for r in rows]

        output_path = args.output or f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(backup, f, indent=2, ensure_ascii=False, default=str)

        _output({'status': 'backed_up', 'file': output_path, 'tables': len(tables)}, args.format)


# ── health ─────────────────────────────────────────────────────────

def cmd_health(args):
    app = _get_app()
    with app.app_context():
        try:
            db.session.execute(text('SELECT 1'))
            db_ok = True
        except Exception:
            db_ok = False

        data = {
            'status': 'ok' if db_ok else 'degraded',
            'database': 'connected' if db_ok else 'disconnected',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    _output(data, args.format)


# ── analyze (dry-run) ──────────────────────────────────────────────

def cmd_analyze(args):
    from utils.validators import validate_dwar_url
    url = args.url
    valid, error = validate_dwar_url(url)
    if not valid:
        _output({'status': 'error', 'error': error}, args.format)
        sys.exit(1)

    if args.dry_run:
        _output({
            'status': 'dry_run',
            'url': url,
            'validated': True,
            'message': 'URL is valid. In production, this would fetch and parse the character page.',
        }, args.format)
        return

    _output({'status': 'ok', 'url': url}, args.format)


# ── main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='dwar-rater-cli',
        description='Dwar Rater management CLI',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # users
    users_p = sub.add_parser('users', help='Manage users')
    users_sub = users_p.add_subparsers(dest='action', required=True)

    users_list_p = users_sub.add_parser('list', help='List users')
    users_list_p.add_argument('--format', choices=['table', 'json'], default='table')
    users_list_p.set_defaults(func=cmd_users_list)

    users_create_p = users_sub.add_parser('create', help='Create user')
    users_create_p.add_argument('--username', required=True)
    users_create_p.add_argument('--password', required=True)
    users_create_p.add_argument('--role', default='user', choices=['user', 'admin'])
    users_create_p.add_argument('--format', choices=['table', 'json'], default='table')
    users_create_p.set_defaults(func=cmd_users_create)

    users_delete_p = users_sub.add_parser('delete', help='Delete user')
    users_delete_p.add_argument('--username', required=True)
    users_delete_p.add_argument('--format', choices=['table', 'json'], default='table')
    users_delete_p.set_defaults(func=cmd_users_delete)

    # cache
    cache_p = sub.add_parser('cache', help='Manage cache')
    cache_sub = cache_p.add_subparsers(dest='action', required=True)

    cache_clear_p = cache_sub.add_parser('clear', help='Clear cache')
    cache_clear_p.add_argument('--nick', help='Clear cache for specific nick')
    cache_clear_p.add_argument('--format', choices=['table', 'json'], default='table')
    cache_clear_p.set_defaults(func=cmd_cache_clear)

    cache_list_p = cache_sub.add_parser('list', help='List cached entries')
    cache_list_p.add_argument('--format', choices=['table', 'json'], default='table')
    cache_list_p.set_defaults(func=cmd_cache_list)

    # db
    db_p = sub.add_parser('db', help='Database operations')
    db_sub = db_p.add_subparsers(dest='action', required=True)

    db_status_p = db_sub.add_parser('status', help='Show database status')
    db_status_p.add_argument('--format', choices=['table', 'json'], default='table')
    db_status_p.set_defaults(func=cmd_db_status)

    db_backup_p = db_sub.add_parser('backup', help='Backup database to JSON')
    db_backup_p.add_argument('--output', '-o', help='Output file path')
    db_backup_p.add_argument('--format', choices=['table', 'json'], default='table')
    db_backup_p.set_defaults(func=cmd_db_backup)

    # health
    health_p = sub.add_parser('health', help='Health check')
    health_p.add_argument('--format', choices=['table', 'json'], default='table')
    health_p.set_defaults(func=cmd_health)

    # analyze
    analyze_p = sub.add_parser('analyze', help='Validate/analyze URL')
    analyze_p.add_argument('--url', required=True)
    analyze_p.add_argument('--dry-run', action='store_true')
    analyze_p.add_argument('--format', choices=['table', 'json'], default='table')
    analyze_p.set_defaults(func=cmd_analyze)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
