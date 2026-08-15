#!/usr/bin/env python
"""Validate that openapi.yaml covers all Flask routes.

Usage:
    python scripts/generate_openapi.py          # just validate
    python scripts/generate_openapi.py --check  # exit 1 if stale

This script extracts all route paths from Flask blueprints and compares
them against the paths defined in docs/openapi.yaml.
"""

import os
import re
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

FEATURES_DIR = os.path.join(BASE_DIR, 'features')
OPENAPI_PATH = os.path.join(BASE_DIR, 'docs', 'openapi.yaml')


def normalize_path(path):
    """Normalize path params: Flask <int:x> -> {x}, Flask <x> -> {x}."""
    return re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', path)


def extract_routes_from_file(filepath):
    """Extract route paths and methods from a Flask blueprint file."""
    routes = set()
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Matches both single-line and multi-line decorators:
    #   @bp.route('/path', methods=['GET', 'POST'])
    #   @bp.route(
    #       '/path', methods=['GET']
    #   )
    pattern = re.compile(
        r"@(\w+)\.route\(\s*['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?\s*\)",
        re.DOTALL
    )
    for match in pattern.finditer(content):
        bp_var = match.group(1)
        path = match.group(2)
        methods_str = match.group(3)

        if methods_str:
            methods = [m.strip().strip("'\"") for m in methods_str.split(',')]
        else:
            methods = ['GET']

        normalized = normalize_path(path)
        for method in methods:
            routes.add(f"{method.upper()} {normalized}")

    return routes


def extract_routes_from_features(features_dir):
    """Extract route paths and methods from all features/*/routes.py files."""
    routes = set()
    if not os.path.isdir(features_dir):
        print(f"ERROR: features dir not found at {features_dir}")
        sys.exit(1)
    for entry in sorted(os.listdir(features_dir)):
        routes_file = os.path.join(features_dir, entry, 'routes.py')
        if os.path.isfile(routes_file):
            routes.update(extract_routes_from_file(routes_file))
    return routes


def extract_paths_from_openapi(filepath):
    """Extract paths from OpenAPI YAML (simple regex, no YAML parser needed)."""
    routes = set()
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    current_path = None
    for line in content.split('\n'):
        path_match = re.match(r'^  (/\S+):', line)
        if path_match:
            current_path = path_match.group(1)
            continue

        method_match = re.match(r'^    (get|post|put|delete|patch|head|options):', line)
        if method_match and current_path:
            method = method_match.group(1).upper()
            routes.add(f"{method} {current_path}")

    return routes


def main():
    check_mode = '--check' in sys.argv

    all_routes = extract_routes_from_features(FEATURES_DIR)

    if not os.path.exists(OPENAPI_PATH):
        print(f"ERROR: OpenAPI spec not found at {OPENAPI_PATH}")
        sys.exit(1)

    openapi_routes = extract_paths_from_openapi(OPENAPI_PATH)

    missing = all_routes - openapi_routes
    extra = openapi_routes - all_routes

    print(f"Routes in code:    {len(all_routes)}")
    print(f"Routes in OpenAPI: {len(openapi_routes)}")

    if missing:
        print(f"\nMISSING from OpenAPI ({len(missing)}) — documentation debt, tracked in ROADMAP P4:")
        for route in sorted(missing):
            print(f"  - {route}")

    if extra:
        print(f"\nEXTRA in OpenAPI (not in code) ({len(extra)}) — STALE DOCS, must be removed:")
        for route in sorted(extra):
            print(f"  - {route}")

    if not missing and not extra:
        print("\nAPI docs are up to date.")
        sys.exit(0)
    elif extra:
        print(f"\nAPI docs are OUT OF DATE (stale endpoints documented).")
        print("Remove the EXTRA paths from docs/openapi.yaml.")
        sys.exit(1)
    else:
        print(f"\nAPI docs are PARTIAL (missing {len(missing)} endpoints) — allowed.")
        sys.exit(0)


if __name__ == '__main__':
    main()
