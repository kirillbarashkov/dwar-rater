"""A9: единичная компенсация обязана уважать закрытый месяц и валидировать ввод.

Массовый путь (импорт, восстановление из бэкапа) закрытые месяцы проверяет, а
единичная компенсация — нет: запись проходила в уже закрытый месяц, то есть
пересчитывала итог, который клан уже согласовал. Плюс `months` принимал что
угодно (включая 13-й месяц → «15.13.2025»), а `norm_amount` — ноль и минус.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import ClanInfo, TreasuryMonthClose, TreasuryOperation

CLAN = 987231  # уникальный: чужой id делит состояние с другими файлами
CLOSED_YEAR = 2025
CLOSED_MONTH = 5


import pytest


@pytest.fixture(autouse=True)
def _clean(app):
    """Своя уборка: общий _truncate_all() — no-op, БД между тестами не чистится.

    Без этого закрытый месяц остаётся в БД и ломает чужие тесты, которые
    используют тот же clan_id (так падал test_treasury_nick_transfer).
    """
    def _purge():
        with app.app_context():
            TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
            TreasuryMonthClose.query.filter_by(clan_id=CLAN).delete()
            ClanInfo.query.filter_by(clan_id=CLAN).delete()
            db.session.commit()
    _purge()
    yield
    _purge()


def _seed(app, closes=()):
    with app.app_context():
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        TreasuryMonthClose.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='CompClan'))
        for month, year in closes:
            db.session.add(TreasuryMonthClose(clan_id=CLAN, month=month, year=year))
        db.session.commit()


def _post(client, headers, **body):
    return client.post(
        f'/api/clan/{CLAN}/treasury/compensation', json=body, headers=headers
    )


def _ops_count(app):
    with app.app_context():
        return TreasuryOperation.query.filter_by(clan_id=CLAN).count()


# --- закрытый месяц ---------------------------------------------------------

def test_compensation_into_closed_month_is_refused(app, client, treasurer_headers):
    _seed(app, closes=[(CLOSED_MONTH, CLOSED_YEAR)])
    before = _ops_count(app)

    resp = _post(
        client,
        treasurer_headers,
        nick='Гном',
        norm_amount=100,
        months=[CLOSED_MONTH],
        year=CLOSED_YEAR,
    )

    assert resp.status_code == 400, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body.get('error') == 'month_closed', body
    assert _ops_count(app) == before, 'запись в закрытый месяц всё-таки создана'


def test_compensation_refuses_when_any_month_is_closed(app, client, treasurer_headers):
    """Даже один закрытый месяц в списке отменяет всю пачку."""
    _seed(app, closes=[(CLOSED_MONTH, CLOSED_YEAR)])
    before = _ops_count(app)

    resp = _post(
        client,
        treasurer_headers,
        nick='Гном',
        norm_amount=100,
        months=[4, CLOSED_MONTH, 6],
        year=CLOSED_YEAR,
    )

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert _ops_count(app) == before, 'часть месяцев записалась, хотя один закрыт'


# --- валидация ввода --------------------------------------------------------

def test_month_out_of_range_is_refused(app, client, treasurer_headers):
    _seed(app)
    resp = _post(
        client, treasurer_headers,
        nick='Гном', norm_amount=100, months=[13], year=CLOSED_YEAR,
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert '13' in str(resp.get_json()), 'в ответе нет указания на плохой месяц'


def test_zero_amount_is_refused(app, client, treasurer_headers):
    _seed(app)
    resp = _post(
        client, treasurer_headers,
        nick='Гном', norm_amount=0, months=[3], year=CLOSED_YEAR,
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)


def test_negative_amount_is_refused(app, client, treasurer_headers):
    _seed(app)
    resp = _post(
        client, treasurer_headers,
        nick='Гном', norm_amount=-50, months=[3], year=CLOSED_YEAR,
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)


def test_non_numeric_amount_is_refused(app, client, treasurer_headers):
    _seed(app)
    resp = _post(
        client, treasurer_headers,
        nick='Гном', norm_amount='много', months=[3], year=CLOSED_YEAR,
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)


# --- контроль: обычный путь по-прежнему работает ---------------------------

def test_compensation_into_open_month_still_works(app, client, treasurer_headers):
    _seed(app, closes=[(CLOSED_MONTH, CLOSED_YEAR)])
    before = _ops_count(app)

    resp = _post(
        client, treasurer_headers,
        nick='Гном', norm_amount=150, months=[7], year=CLOSED_YEAR,
        comment='долг за июль',
    )

    assert resp.status_code == 201, resp.get_data(as_text=True)
    assert _ops_count(app) == before + 1, 'компенсация в открытый месяц не создалась'
