#!/usr/bin/env python3
"""Version management utilities for dwar-rater.

Strategy: env-first. In production, build/deploy metadata is injected via
ARG/ENV at image build time (see backend/Dockerfile and .github/workflows/deploy.yml).
Local dev falls back to the VERSION file, git, and file mtime.
"""

import os
import subprocess
import json
from datetime import datetime, timezone


VERSION_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'VERSION')


def _run_git(*args):
    """Run a git command at the repo root; return stripped output or None."""
    try:
        return subprocess.check_output(
            ['git', *args],
            cwd=os.path.dirname(VERSION_FILE),
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def read_version():
    """Current version: APP_VERSION env → VERSION file → '0.0.0'."""
    env_val = os.environ.get('APP_VERSION')
    if env_val:
        return env_val
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip() or '0.0.0'
    except (FileNotFoundError, OSError):
        return '0.0.0'


def read_git_hash():
    """Short commit hash: APP_GIT_HASH env → git → 'unknown'."""
    env_val = os.environ.get('APP_GIT_HASH')
    if env_val:
        return env_val
    return _run_git('rev-parse', '--short', 'HEAD') or 'unknown'


def read_build_date():
    """Build date: APP_BUILD_DATE env → VERSION file mtime → now (UTC)."""
    env_val = os.environ.get('APP_BUILD_DATE')
    if env_val:
        return env_val
    try:
        stat = os.stat(VERSION_FILE)
        return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    except OSError:
        return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def read_branch():
    """Branch name: APP_BRANCH env → git → 'unknown'."""
    env_val = os.environ.get('APP_BRANCH')
    if env_val:
        return env_val
    return _run_git('rev-parse', '--abbrev-ref', 'HEAD') or 'unknown'


def bump_version(part='patch'):
    """Bump version: major.minor.patch → writes VERSION file, returns new version.

    Dev/CI utility only — never called from runtime request paths.
    """
    version = read_version()
    parts = version.split('.')
    if len(parts) != 3:
        return '1.0.0'

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if part == 'major':
        major += 1
        minor = 0
        patch = 0
    elif part == 'minor':
        minor += 1
        patch = 0
    else:  # patch
        patch += 1

    new_version = f'{major}.{minor}.{patch}'
    with open(VERSION_FILE, 'w') as f:
        f.write(new_version + '\n')

    return new_version


def get_version_info():
    """Get complete version information."""
    return {
        'version': read_version(),
        'git_hash': read_git_hash(),
        'build_date': read_build_date(),
        'branch': read_branch(),
    }


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        new_ver = bump_version(sys.argv[1])
        print(f'Version bumped to {new_ver}')
    else:
        print(json.dumps(get_version_info(), indent=2))
