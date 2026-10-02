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
    # The request is older than the stored boundary, so the source is probed
    # with the ORIGINAL start first (a saturated answer may correct a boundary
    # that is too new) and the range is trimmed only afterwards.
    assert seen and seen[0][0] == "01.01.2026", seen
    assert seen[-1][0] == BOUNDARY, seen
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


def test_boundary_storage_is_last_write_wins(app):
    """The setter writes through: the saturation guard lives in the caller.

    Forward-only storage made a wrong (too-new) boundary permanent, freezing
    every older period, so correction has to be possible.
    """
    from features.clan_info import routes as routes

    with app.app_context():
        routes.remember_source_window(CLAN, "30.09.2026", 442)
        routes.remember_source_window(CLAN, BOUNDARY, 442)
        row = TreasurySourceWindow.query.filter_by(clan_id=CLAN).first()
        assert row.oldest_date == BOUNDARY
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


def test_narrow_recent_range_does_not_learn_a_boundary(app, client, admin_headers, monkeypatch):
    """A single-day estimate for a recent date must not move the boundary.

    Regression: `oldest_page_earliest` is the oldest op in the *requested*
    range, so learning it made the window jump to 30.09.2026 and refuse every
    older period.
    """
    from features.clan_info import routes as routes

    def _recent(session, start, end, *a, **k):
        return {
            "start_page": 48,
            "end_page": 51,  # not the report's last page (441)
            "estimated_pages": 4,
            "total_pages": 442,
            "sample_dates": {
                "page_0_latest": "20261002",
                "oldest_page_earliest": "202609082047",
            },
        }

    monkeypatch.setattr(routes, "estimate_pages_in_range", _recent)

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/estimate",
        headers=admin_headers,
        json={"start_date": "09.09.2026", "end_date": "09.09.2026"},
    )
    assert resp.status_code == 200
    with app.app_context():
        assert TreasurySourceWindow.query.filter_by(clan_id=CLAN).first() is None


def test_saturated_run_corrects_a_boundary_that_is_too_new(app, client, admin_headers, monkeypatch):
    """A saturated run reports the truth, so it may move the boundary back."""
    from features.clan_info import routes as routes

    with app.app_context():
        db.session.add(
            TreasurySourceWindow(clan_id=CLAN, oldest_date="30.09.2026", total_pages=442)
        )
        db.session.commit()

    monkeypatch.setattr(routes, "estimate_pages_in_range", _saturating_estimate)

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/estimate",
        headers=admin_headers,
        json={"start_date": "01.01.2025", "end_date": "31.10.2026"},
    )
    assert resp.status_code == 200
    with app.app_context():
        row = TreasurySourceWindow.query.filter_by(clan_id=CLAN).first()
        assert row is not None and row.oldest_date == BOUNDARY
