"""A16: сбой при оценке границ казны больше не глушится.

`estimate_pages_in_range` определяет границы сетевыми запросами к dwar.ru. Раньше
сбой этих запросов ловился `except Exception: pass`, и функция возвращала
`sample_dates` без границ как ни в чём не бывало: автосбор стартовал с неверного
диапазона, а причины не было ни в логе, ни в ответе.

Теперь причина попадает в лог, а в результате появляется
`boundaries_complete=False` и список `boundary_errors`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shared.services.clan_parser as cp

OPS = [
    {"date": "15.05.2025 12:00", "nick": "Гном", "quantity": 10},
    {"date": "15.07.2025 12:00", "nick": "Гном", "quantity": 20},
]


class _Logger:
    def __init__(self):
        self.warnings = []

    def warning(self, msg, *a, **kw):
        self.warnings.append(msg)

    def info(self, msg, *a, **kw):
        pass


def _patch(monkeypatch, fetch, logger=None):
    monkeypatch.setattr(cp, "fetch_clan_treasury_report", fetch)
    monkeypatch.setattr(cp, "parse_clan_treasury_operations", lambda html: list(OPS))
    monkeypatch.setattr(cp, "parse_total_pages", lambda html: 20)
    if logger is not None:
        monkeypatch.setattr(cp, "data_logger", logger)


def _estimate():
    return cp.estimate_pages_in_range(
        session=None, start_date_str="01.01.2025", end_date_str="31.12.2025"
    )


def test_boundary_failure_is_reported_not_swallowed(monkeypatch):
    """Сеть отвалилась на страницах-границах: результат помечен как неполный."""
    log = _Logger()

    def fetch_fails(session=None, page=0, filters=None):
        if page != 0:                      # страница 0 нужна для total_pages
            raise RuntimeError("network down")
        return "<html></html>", session

    _patch(monkeypatch, fetch_fails, log)
    result = _estimate()

    assert result["boundaries_complete"] is False, (
        "сбой границ не отмечен в результате — автосбор поедет по неверному диапазону"
    )
    assert result["boundary_errors"], "причина сбоя не сохранена"
    assert any("network down" in e for e in result["boundary_errors"])
    assert log.warnings, "сбой не попал в лог"


def test_happy_path_is_marked_complete(monkeypatch):
    """Контроль: без сбоев результат помечен как полный, ошибок нет."""
    log = _Logger()

    def fetch_ok(session=None, page=0, filters=None):
        return "<html></html>", session

    _patch(monkeypatch, fetch_ok, log)
    result = _estimate()

    assert result["boundaries_complete"] is True
    assert result["boundary_errors"] == []
    assert result["estimated_pages"] >= 0


def test_no_data_in_range_is_not_a_failure(monkeypatch):
    """Пустой диапазон — не ошибка границ: запросы не падали."""
    log = _Logger()

    def fetch_ok(session=None, page=0, filters=None):
        return "<html></html>", session

    _patch(monkeypatch, fetch_ok, log)
    # start_date новее всех операций → ранний возврат «нет данных»
    result = cp.estimate_pages_in_range(
        session=None, start_date_str="01.01.2026", end_date_str="31.12.2026"
    )

    assert result["estimated_pages"] == 0
    assert result["boundaries_complete"] is True, (
        'пустой диапазон не должен помечаться как сбой границ'
    )
