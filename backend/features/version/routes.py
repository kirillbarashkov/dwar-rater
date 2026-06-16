import os
import subprocess
import requests
from flask import Blueprint, jsonify, request, g
from shared.rbac import require_permission
from shared.utils.version import get_version_info, bump_version

version_bp = Blueprint('version', __name__)


@version_bp.route('/api/version', methods=['GET'])
def version_info():
    """Public endpoint — returns current version info."""
    return jsonify(get_version_info())


@version_bp.route('/api/version/bump', methods=['POST'])
@require_permission('admin', 'deploy')
def bump_version_endpoint():
    """Admin only — bump version and return new version."""
    data = request.get_json(silent=True) or {}
    part = data.get('part', 'patch')

    if part not in ('major', 'minor', 'patch'):
        return jsonify({'error': 'Invalid bump part. Use: major, minor, or patch'}), 400

    new_version = bump_version(part)
    return jsonify({
        'version': new_version,
        'message': f'Version bumped to {new_version}',
    })


@version_bp.route('/api/admin/deploy', methods=['POST'])
@require_permission('admin', 'deploy')
def trigger_deploy():
    """Admin only — create PR dev→main via GitHub API and return changelog."""
    data = request.get_json(silent=True) or {}
    bump_part = data.get('bump_part', 'patch')

    github_token = os.environ.get('GITHUB_TOKEN')
    github_repo = os.environ.get('GITHUB_REPO', 'kirillbarashkov/dwar-rater')

    if not github_token:
        return jsonify({'error': 'GITHUB_TOKEN not configured'}), 500

    try:
        # 1. Bump version first
        new_version = bump_version(bump_part)

        # 2. Get commits between dev and main
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json',
        }

        # Get commits on dev that are not on main
        compare_url = f'https://api.github.com/repos/{github_repo}/compare/main...dev'
        resp = requests.get(compare_url, headers=headers, timeout=10)
        resp.raise_for_status()
        compare_data = resp.json()

        commits = compare_data.get('commits', [])
        changelog = []
        for commit in commits:
            msg = commit.get('commit', {}).get('message', '')
            # Skip merge commits
            if msg.startswith('Merge '):
                continue
            sha = commit.get('sha', '')[:7]
            changelog.append({
                'sha': sha,
                'message': msg.split('\n')[0],  # First line only
                'author': commit.get('commit', {}).get('author', {}).get('name', ''),
                'date': commit.get('commit', {}).get('author', {}).get('date', ''),
            })

        # 3. Create PR
        pr_title = f'Release v{new_version}'
        pr_body = f'## Release v{new_version}\n\n'
        pr_body += f'**Bump type:** {bump_part}\n\n'
        pr_body += '### Changes\n\n'
        for item in changelog:
            pr_body += f'- `{item["sha"]}` {item["message"]} ({item["author"]})\n'

        pr_resp = requests.post(
            f'https://api.github.com/repos/{github_repo}/pulls',
            headers=headers,
            json={
                'title': pr_title,
                'body': pr_body,
                'head': 'dev',
                'base': 'main',
            },
            timeout=10,
        )

        if pr_resp.status_code == 422:
            # PR already exists
            return jsonify({
                'status': 'pr_exists',
                'message': 'PR dev→main already exists. Merge it first.',
                'version': new_version,
                'changelog': changelog,
            })

        pr_resp.raise_for_status()
        pr_data = pr_resp.json()

        return jsonify({
            'status': 'pr_created',
            'message': f'PR #{pr_data["number"]} created',
            'pr_url': pr_data.get('html_url'),
            'pr_number': pr_data.get('number'),
            'version': new_version,
            'changelog': changelog,
        })

    except requests.RequestException as e:
        return jsonify({'error': f'GitHub API error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Deploy error: {str(e)}'}), 500


@version_bp.route('/api/admin/deploy/status', methods=['GET'])
@require_permission('admin', 'deploy')
def deploy_status():
    """Check CI/CD workflow status for latest main push."""
    github_token = os.environ.get('GITHUB_TOKEN')
    github_repo = os.environ.get('GITHUB_REPO', 'kirillbarashkov/dwar-rater')

    if not github_token:
        return jsonify({'error': 'GITHUB_TOKEN not configured'}), 500

    try:
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json',
        }

        # Get latest workflow runs for deploy.yml
        runs_resp = requests.get(
            f'https://api.github.com/repos/{github_repo}/actions/runs',
            headers=headers,
            params={
                'branch': 'main',
                'per_page': 5,
            },
            timeout=10,
        )
        runs_resp.raise_for_status()
        runs = runs_resp.json().get('workflow_runs', [])

        # Find the deploy workflow
        deploy_run = None
        for run in runs:
            if 'deploy' in run.get('name', '').lower():
                deploy_run = run
                break

        if not deploy_run:
            return jsonify({'status': 'unknown', 'message': 'No recent deploy workflow found'})

        return jsonify({
            'status': deploy_run.get('status'),  # queued, in_progress, completed
            'conclusion': deploy_run.get('conclusion'),  # success, failure
            'updated_at': deploy_run.get('updated_at'),
            'html_url': deploy_run.get('html_url'),
        })

    except requests.RequestException as e:
        return jsonify({'error': f'GitHub API error: {str(e)}'}), 500
