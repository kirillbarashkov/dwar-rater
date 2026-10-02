"""Treasury import resilience + coverage range correctness.

Two follow-ups from the 2026-10-02 investigation:

1. A page that parses to zero operations used to end the fetch walk silently —
   the caller saw `success: true`, a short list and no explanation.
2. `date-coverage` reported `earliest_date` / `latest_date` via lexicographic
   min/max over "DD.MM.YYYY" strings, so a January date looked "earlier" than
   the previous December.
"""
from shared.models import db
from shared.models.clan_info import ClanCookie, ClanInfo, TreasuryOperation

import pytest

CLAN = 987003  # fetch-walk tests
CLAN_COVERAGE = 987004  # coverage-ordering test

CHROME_ROWS = '<tr height="19"><td width="20">&nbsp;</td></tr>' * 30

# A real report page is tens of KB (the row markup is padded with chrome rows
# around it), so both fixtures must clear the "stub answer" size guard.
PAGE_HTML = f"""<html><body><table>{CHROME_ROWS}
<tr class="bg_l"><td class="brd-all p6h">09.09.2026 20:05</td>
  <td class="brd-all p6h">userToTag('_ Sanych_')</td>
  <td class="brd-all p6h">Деньги</td>
  <td class="brd-all p6h"><a>Монеты</a></td>
  <td class="brd-all p6h"><span style="color: green">100</span></td></tr>
{CHROME_ROWS}</table></body></html>
"""

# A real report page with no operations: chrome only. This is how dwar answers
# past the end of the history.
EMPTY_PAGE_HTML = (
    "<html><body><table>" + (CHROME_ROWS * 2) + "</table></body></html>"
)
TINY_HTML = "<html><body>" + ("x" * 50) + "</body></html>"


def _seed_clan(app, clan_id):
    """Treasury rows FK to clan_info, so the clan must exist first."""
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=clan_id).first():
            db.session.add(ClanInfo(clan_id=clan_id, name="TestClan"))
            db.session.commit()


@pytest.fixture(autouse=True)
def _cookie(app):
    _seed_clan(app, CLAN)
    _seed_clan(app, CLAN_COVERAGE)
    with app.app_context():
        row = ClanCookie.query.filter_by(clan_id=CLAN).first()
        if row is None:
            db.session.add(
                ClanCookie(clan_id=CLAN, cookie_string="sess_sid=x", is_valid=True)
            )
        else:
            row.is_valid = True
        db.session.commit()
    yield


def _pages(mapping):
    def _inner(session=None, page=0, filters=None):
        return mapping.get(page, EMPTY_PAGE_HTML), session

    return _inner


def _fetch(client, admin_headers, end_page):
    return client.post(
        f"/api/clan/{CLAN}/treasury/auto-fetch-json",
        headers=admin_headers,
        json={"start_date": "01.01.2025", "start_page": 0, "end_page": end_page},
    ).get_json()


def test_tiny_answer_stops_the_walk_loudly(app, client, admin_headers, monkeypatch):
    from features.clan_info import routes as routes

    monkeypatch.setattr(routes, "fetch_clan_treasury_report", _pages({0: TINY_HTML}))

    body = _fetch(client, admin_headers, end_page=2)
    assert body["success"] is True, body
    assert body["stopped_early"] is True, body
    assert "пустой ответ" in body["warning"]
    assert "Повторите сбор" in body["message"]


def test_empty_page_before_the_last_one_is_reported(app, client, admin_headers, monkeypatch):
    from features.clan_info import routes as routes

    # pages 0,1,2 requested; page 1 comes back empty -> walk cut short
    monkeypatch.setattr(
        routes,
        "fetch_clan_treasury_report",
        _pages({0: PAGE_HTML, 1: EMPTY_PAGE_HTML}),
    )

    body = _fetch(client, admin_headers, end_page=3)
    assert body["success"] is True, body
    assert body["stopped_early"] is True, body
    assert "не содержит операций" in body["warning"]
    assert len(body["operations"]) == 1, body


def test_natural_end_of_the_report_is_not_flagged(app, client, admin_headers, monkeypatch):
    from features.clan_info import routes as routes

    # page 1 is the last requested page and it is empty -> the report just ended
    monkeypatch.setattr(
        routes,
        "fetch_clan_treasury_report",
        _pages({0: PAGE_HTML, 1: EMPTY_PAGE_HTML}),
    )

    body = _fetch(client, admin_headers, end_page=2)
    assert body["success"] is True, body
    assert body["stopped_early"] is False, body
    assert body["warning"] is None, body
    assert "Повторите сбор" not in body["message"]


def test_coverage_dates_are_chronological(app, client, admin_headers):
    with app.app_context():
        TreasuryOperation.query.filter_by(clan_id=CLAN_COVERAGE).delete()
        for date in ("31.12.2025 10:00", "01.01.2026 10:00", "15.06.2026 12:00"):
            db.session.add(
                TreasuryOperation(
                    clan_id=CLAN_COVERAGE,
                    date=date,
                    nick="Tester",
                    operation_type="Склад",
                    object_name="Объект",
                    quantity=1,
                )
            )
        db.session.commit()

    resp = client.get(
        f"/api/clan/{CLAN_COVERAGE}/treasury/date-coverage", headers=admin_headers
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["earliest_date"] == "31.12.2025", body
    assert body["latest_date"] == "15.06.2026", body
