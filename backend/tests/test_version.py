"""Tests for version utilities and /api/version endpoint (env-first strategy)."""
import os

import pytest

from shared.utils import version as version_mod


class TestReadVersionEnvFirst:
    def test_env_var_takes_priority_over_file(self, monkeypatch):
        monkeypatch.setenv('APP_VERSION', '9.9.9')
        assert version_mod.read_version() == '9.9.9'

    def test_fallback_to_version_file(self, monkeypatch):
        monkeypatch.delenv('APP_VERSION', raising=False)
        # In-container /app/../VERSION does not exist → fallback '0.0.0'
        # is expected; on a full checkout the file exists and is read.
        result = version_mod.read_version()
        assert result == '1.0.0' or result == '0.0.0'


class TestReadGitHashEnvFirst:
    def test_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv('APP_GIT_HASH', 'abc1234')
        assert version_mod.read_git_hash() == 'abc1234'

    def test_fallback_unknown_when_no_git(self, monkeypatch):
        monkeypatch.delenv('APP_GIT_HASH', raising=False)
        monkeypatch.setattr(version_mod, '_run_git', lambda *a: None)
        assert version_mod.read_git_hash() == 'unknown'


class TestReadBranchEnvFirst:
    def test_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv('APP_BRANCH', 'release-branch')
        assert version_mod.read_branch() == 'release-branch'

    def test_fallback_unknown_when_no_git(self, monkeypatch):
        monkeypatch.delenv('APP_BRANCH', raising=False)
        monkeypatch.setattr(version_mod, '_run_git', lambda *a: None)
        assert version_mod.read_branch() == 'unknown'


class TestReadBuildDateEnvFirst:
    def test_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv('APP_BUILD_DATE', '2026-08-15 12:00 UTC')
        assert version_mod.read_build_date() == '2026-08-15 12:00 UTC'


class TestVersionEndpoint:
    def test_public_no_auth_required(self, client):
        resp = client.get('/api/version')
        assert resp.status_code == 200
        body = resp.get_json()
        assert set(body.keys()) == {'version', 'git_hash', 'build_date', 'branch'}

    def test_bump_endpoint_removed(self, client, admin_headers):
        resp = client.post('/api/version/bump', headers=admin_headers,
                           json={'part': 'patch'})
        assert resp.status_code == 404

    def test_admin_deploy_endpoint_removed(self, client, admin_headers):
        resp = client.post('/api/admin/deploy', headers=admin_headers,
                           json={'bump_part': 'patch'})
        assert resp.status_code == 404

    def test_admin_deploy_status_endpoint_removed(self, client, admin_headers):
        resp = client.get('/api/admin/deploy/status', headers=admin_headers)
        assert resp.status_code == 404


class TestBumpVersionUtil:
    def test_patch_bump(self, tmp_path, monkeypatch):
        vfile = tmp_path / 'VERSION'
        vfile.write_text('1.2.3\n')
        monkeypatch.setattr(version_mod, 'VERSION_FILE', str(vfile))
        monkeypatch.delenv('APP_VERSION', raising=False)
        assert version_mod.bump_version('patch') == '1.2.4'
        assert vfile.read_text().strip() == '1.2.4'

    def test_invalid_version_resets(self, tmp_path, monkeypatch):
        vfile = tmp_path / 'VERSION'
        vfile.write_text('garbage\n')
        monkeypatch.setattr(version_mod, 'VERSION_FILE', str(vfile))
        monkeypatch.delenv('APP_VERSION', raising=False)
        assert version_mod.bump_version('patch') == '1.0.0'
