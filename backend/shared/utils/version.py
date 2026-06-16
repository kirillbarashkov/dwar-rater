#!/usr/bin/env python3
"""Version management utilities for dwar-rater."""

import os
import subprocess
import json
from datetime import datetime, timezone


VERSION_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'VERSION')


def read_version():
    """Read current version from VERSION file."""
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return '0.0.0'


def read_git_hash():
    """Get current git commit hash."""
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=os.path.dirname(VERSION_FILE),
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 'unknown'


def read_build_date():
    """Get build/deploy date."""
    try:
        stat = os.stat(VERSION_FILE)
        return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    except OSError:
        return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def read_branch():
    """Get current git branch."""
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=os.path.dirname(VERSION_FILE),
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 'unknown'


def bump_version(part='patch'):
    """Bump version: major.minor.patch → returns new version string."""
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
