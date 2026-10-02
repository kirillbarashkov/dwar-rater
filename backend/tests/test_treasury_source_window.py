"""Learned 'source window': dwar purges treasury history after ~6 months.

The boundary is learned from real attempts (no probing), stored per clan, and
used to answer honestly instead of returning an empty but "successful" result.
Regression for the 2026-10-02 report: a range older than the window made the
estimate answer "1 страница" pointing at a page from another month, the fetch
then returned `success: true` with zero operations and the UI silently reset.
"""
from shared.models import db
from shared.models.clan_info import ClanCookie, TreasurySourceWindow

import pytest

CLAN = 987002  # dedicated id, not shared with other test modules
BOUNDARY = "05.04.2026"


@pytest.fixture(autouse=True)
def _clean_window(app):
    """Each test starts with no learned boundary but valid cookies (clan_id is unique)."""
    with app.app_context():
        TreasurySourceWindow.query.filter_by(clan_id=CLAN).delete()
        cookie = ClanCookie.query.filter_by(clan_id=CLAN).first()
        if cookie is None:
            db.session.add(
                ClanCookie(clan_id=CLAN, cookie_string="sess_sid=x", is_valid=True)
            )
        else:
            cookie.is_valid = True
        db.session.commit()
    yield


def _store_boundary():
    row = TreasurySourceWindow.query.filter_by(clan_id=CLAN).first()
    if row is None:
        row = TreasurySourceWindow(clan_id=CLAN)
        db.session.add(row)
    row.oldest_date = BOUNDARY
    row.total_pages = 442
    db.session.commit()


def _saturating_estimate(*_args, **_kwargs):
    """What the estimate returns when the range reaches the report's end."""
    return {
        "start_page": 0,
        "end_page": 441,
        "estimated_pages": 442,
        "total_pages": 442,
        "sample_dates": {
            "page_0_latest": "20261002",
            "oldest_page_earliest": "202604050702",
            "oldest_page_latest": "202604050858",
        },
    }


def test_estimate_refuses_range_entirely_older_than_window(
    app, client, admin_headers, monkeypatch
):
    with app.app_context():
        _store_boundary()

    from features.clan_info import routes as routes

    def _must_not_fetch(*_a, **_k):
        raise AssertionError("dwar must not be queried for an unavailable range")

    monkeypatch.setattr(routes, "estimate_pages_in_range", _must_not_fetch)

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/estimate",
        headers=admin_headers,
        json={"start_date": "01.01.2026", "end_date": "31.01.2026"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is False, body
    assert body["error"] == "range_unavailable"
    assert body["oldest_available_date"] == BOUNDARY
    assert BOUNDARY in body["message"]


def test_estimate_trims_partially_available_range(app, client, admin_headers, monkeypatch):
    with app.app_context():
        _store_boundary()

    from features.clan_info import routes as routes

    seen = []

    def _fake(session, start, end, *a, **k):
        seen.append((start, end))
        return _saturating_estimate()

    monkeypatch.setattr(routes, "estimate_pages_in_range", _fake)

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/estimate",
        headers=admin_headers,
        json={"start_date": "01.01.2026", "end_date": "30.09.2026"},
    )
    body = resp.get_json()
    assert body["success"] is True, body
    assert seen and seen[0][0] == BOUNDARY, seen
    assert body["trimmed"] is True
    assert body["requested_start_date"] == "01.01.2026"
    assert body["effective_start_date"] == BOUNDARY


def test_estimate_learns_boundary_from_saturating_run(app, client, admin_headers, monkeypatch):
    from features.clan_info import routes as routes

    calls = []

    def _fake(session, start, end, *a, **k):
        calls.append(start)
        if len(calls) == 1:
            # First pass: the search saturates at the report's end and answers
            # with a single page from another month ("1 страница").
            return {
                "start_page": 441,
                "end_page": 441,
                "estimated_pages": 1,
                "total_pages": 442,
                "sample_dates": {
                    "page_0_latest": "20261002",
                    "oldest_page_earliest": "202604050702",
                },
            }
        # Re-run against the learned boundary must describe the real range.
        return _saturating_estimate()

    monkeypatch.setattr(routes, "estimate_pages_in_range", _fake)

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/estimate",
        headers=admin_headers,
        json={"start_date": "01.01.2025"},
    )
    body = resp.get_json()
    assert body["success"] is True, body
    assert body["trimmed"] is True
    assert body["oldest_available_date"] == BOUNDARY
    # the bogus single-page answer must be replaced by the re-estimated range
    assert body["estimated_pages"] == 442, body
    assert len(calls) == 2 and calls[1] == BOUNDARY, calls

    with app.app_context():
        row = TreasurySourceWindow.query.filter_by(clan_id=CLAN).first()
        assert row is not None and row.oldest_date == BOUNDARY
        assert row.total_pages == 442


def test_estimate_with_zero_pages_is_an_explicit_error(app, client, admin_headers, monkeypatch):
    from features.clan_info import routes as routes

    def _zero(*_a, **_k):
        return {
            "start_page": 0,
            "end_page": 0,
            "estimated_pages": 0,
            "total_pages": 442,
            "sample_dates": {"page_0_latest": "202604050858"},
        }

    monkeypatch.setattr(routes, "estimate_pages_in_range", _zero)

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/estimate",
        headers=admin_headers,
        json={"start_date": "01.01.2026", "end_date": "31.01.2026"},
    )
    body = resp.get_json()
    assert body["success"] is False, body
    assert body["error"] == "range_unavailable"


def test_fetch_refuses_range_older_than_window_without_touching_dwar(
    app, client, admin_headers
):
    with app.app_context():
        _store_boundary()
        if not ClanCookie.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanCookie(clan_id=CLAN, cookie_string="sess_sid=x", is_valid=True))
            db.session.commit()

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/auto-fetch-json",
        headers=admin_headers,
        json={"start_date": "01.01.2026", "end_date": "31.01.2026", "start_page": 0, "end_page": 2},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is False, body
    assert body["error"] == "range_unavailable"
    assert body["oldest_available_date"] == BOUNDARY


def test_boundary_only_moves_forward(app):
    from features.clan_info import routes as routes

    with app.app_context():
        routes.remember_source_window(CLAN, BOUNDARY, 442)
        # An older observation (e.g. a stale request) must not un-freeze April.
        routes.remember_source_window(CLAN, "01.01.2026", 900)
        row = TreasurySourceWindow.query.filter_by(clan_id=CLAN).first()
        assert row.oldest_date == BOUNDARY
        # A newer boundary (dwar purged further) is accepted.
        routes.remember_source_window(CLAN, "01.05.2026", 500)
        db.session.refresh(row)
        assert row.oldest_date == "01.05.2026"
        assert row.total_pages == 500


def test_date_coverage_exposes_source_window(app, client, admin_headers):
    with app.app_context():
        row = TreasurySourceWindow.query.filter_by(clan_id=CLAN).first()
        if row is None:
            _store_boundary()

    resp = client.get(f"/api/clan/{CLAN}/treasury/date-coverage", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["source_window"] is not None, body
    assert body["source_window"]["oldest_available_date"] == BOUNDARY
    assert "learned_at" in body["source_window"]
