"""Treasury range-import date logic — regression tests.

Covers the prod bug reported 2026-09-13 («не смог запустить импорт за новые
даты (после 25.07.2026)»): `estimate_pages_in_range` crashed with a TypeError
(``'<=' not supported between 'str' and 'NoneType'``) when `end_date_str` was
None (the default UI flow «от выбранной даты до текущей»), so the binary search
returned a bogus page range (oldest page only) and the import collected 0 ops.

All fetches are mocked — these tests never touch dwar.ru.
"""
import pytest

from shared.services import clan_parser as cp


# --------------------------------------------------------------------------- #
# Date-comparable helpers
# --------------------------------------------------------------------------- #

def test_parse_date_to_comparable_with_time():
    assert cp._parse_date_to_comparable("25.07.2026 14:30") == "202607251430"
    assert cp._parse_date_to_comparable("garbage") == ""


def test_date_str_to_comparable_day_precision():
    assert cp._date_str_to_comparable("25.07.2026") == "20260725"


def test_op_date_day_strips_time():
    assert cp._op_date_day("25.07.2026 23:59") == "20260725"
    assert cp._op_date_day("25.07.2026 00:00") == "20260725"


def test_op_in_range_inclusive_bounds():
    start_day, end_day = "20260725", "20260801"
    # Op exactly on the start day (any time) is IN range.
    assert cp._op_in_range("20260725", start_day, end_day) is True
    assert cp._op_in_range("202607251059", start_day, end_day) is True
    # Op on the end day is IN range.
    assert cp._op_in_range("20260801", start_day, end_day) is True
    # Outside.
    assert cp._op_in_range("20260724", start_day, end_day) is False
    assert cp._op_in_range("20260802", start_day, end_day) is False


def test_op_in_range_no_end_bound():
    start_day = "20260725"
    assert cp._op_in_range("20260725", start_day, None) is True
    assert cp._op_in_range("20261231", start_day, None) is True
    assert cp._op_in_range("20260724", start_day, None) is False


# --------------------------------------------------------------------------- #
# estimate_pages_in_range (mocked dwar.ru)
# --------------------------------------------------------------------------- #

def _build_pages(total_pages, days_per_page=3, ops_per_day=10, end_day="14.09.2026"):
    """page 0 = newest. Returns list[list[op_date_str]]."""
    from datetime import datetime, timedelta
    end = datetime.strptime(end_day, "%d.%m.%Y")
    pages = []
    cursor = end
    for _ in range(total_pages):
        ops = []
        for d in range(days_per_page):
            day = cursor - timedelta(days=d)
            for h in range(ops_per_day):
                ops.append(day.strftime("%d.%m.%Y") + f" {10 + h % 10:02d}:{h:02d}")
        pages.append(ops)
        cursor = cursor - timedelta(days=days_per_page)
    return pages


def _mock_dwar(monkeypatch, pages):
    """Patch clan_parser fetches to serve canned pages (page 0 newest)."""
    state = {"page": 0}

    def fake_fetch(session=None, page=0, filters=None):
        state["page"] = page
        return f"<html page={page}>", session

    def fake_parse(html):
        return [{"date": d} for d in pages[state["page"]]]

    def fake_total(html):
        return len(pages)

    monkeypatch.setattr(cp, "fetch_clan_treasury_report", fake_fetch)
    monkeypatch.setattr(cp, "parse_clan_treasury_operations", fake_parse)
    monkeypatch.setattr(cp, "parse_total_pages", fake_total)
    monkeypatch.setattr(cp, "is_login_redirect", lambda html: False)
    return object()  # dummy session


def test_estimate_without_end_date_does_not_crash(monkeypatch):
    """start only (None end) — the reported prod flow. Must not TypeError."""
    pages = _build_pages(40)
    session = _mock_dwar(monkeypatch, pages)

    result = cp.estimate_pages_in_range(session, "25.07.2026", None)

    assert "error" not in result
    # start=25.07 → oldest page index 17; page 0 (newest) is the range's start.
    assert result["start_page"] == 0
    assert result["end_page"] == 17
    assert result["estimated_pages"] == 18


def test_estimate_with_end_date_full_range(monkeypatch):
    pages = _build_pages(40)
    session = _mock_dwar(monkeypatch, pages)

    result = cp.estimate_pages_in_range(session, "25.07.2026", "01.08.2026")

    # Newest boundary = first page with data <= 01.08 (page 14), oldest = page 17.
    assert result["start_page"] == 14
    assert result["end_page"] == 17
    assert result["estimated_pages"] == 4


def test_estimate_future_start_is_zero(monkeypatch):
    pages = _build_pages(40)
    session = _mock_dwar(monkeypatch, pages)

    result = cp.estimate_pages_in_range(session, "01.10.2026", None)

    assert result["estimated_pages"] == 0


def test_estimate_includes_start_and_end_day_ops():
    """The day-boundary predicate my rewrite uses: ops on the start/end day count."""
    start_day = cp._date_str_to_comparable("25.07.2026")
    end_day = cp._date_str_to_comparable("01.08.2026")
    # 25.07 op at 22:00 (before the day's 23:59 end) must be in range.
    assert cp._op_in_range(cp._op_date_day("25.07.2026 22:00"), start_day, end_day) is True
    assert cp._op_in_range(cp._op_date_day("01.08.2026 06:00"), start_day, end_day) is True