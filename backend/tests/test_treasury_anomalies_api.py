"""API tests for the treasury anomaly report and the write-boundary guards.

The report is a diagnostic (read-only); the two corruptions it flags — a future
date and a negative amount — are refused on the way in, so new ones cannot be
created. Judgement calls (an unknown nick, an amount above the norm) are never
blocked, only reported.
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import ClanInfo, ClanMemberInfo, TreasuryOperation

CLAN = 987205


def _seed(app, members=(), operations=()):
    with app.app_context():
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='AnomalyClan'))
        for nick in members:
            db.session.add(ClanMemberInfo(clan_id=CLAN, nick=nick, level=5))
        for day, month, year, nick, quantity in operations:
            db.session.add(
                TreasuryOperation(
                    clan_id=CLAN,
                    date=f'{day:02d}.{month:02d}.{year} 12:00',
                    nick=nick,
                    operation_type='Деньги',
                    object_name='Монеты',
                    quantity=quantity,
                )
            )
        db.session.commit()


def _today_pair():
    today = date.today()
    return today.year, today.month


def _future_date():
    """A date in the next month, whatever the wall clock says."""
    year, month = _today_pair()
    month += 1
    if month > 12:
        month = 1
        year += 1
    return 10, month, year


def _report(client, headers):
    return client.get(f'/api/clan/{CLAN}/treasury/anomalies', headers=headers)


def _codes(body):
    return {item['code']: item for item in body['items']}


def _op_id(app):
    with app.app_context():
        return TreasuryOperation.query.filter_by(clan_id=CLAN).first().id


def test_report_requires_auth(app, client):
    _seed(app, members=['Alpha'])
    assert _report(client, None).status_code == 401


def test_report_is_readable_by_a_plain_user(app, client, user_headers):
    _seed(app, members=['Alpha'])
    assert _report(client, user_headers).status_code == 200


def test_a_clean_clan_reports_nothing(app, client, user_headers):
    year, month = _today_pair()
    _seed(app, members=['Alpha'], operations=[(5, month, year, 'Alpha', 10)])
    body = _report(client, user_headers).get_json()
    assert body['items'] == []
    assert body['total'] == 0
    assert body['checked'] == {'operations': 1, 'members': 1}


def test_future_date_and_unknown_nick_are_reported(app, client, user_headers):
    day, month, year = _future_date()
    _seed(app, members=['Alpha'], operations=[(day, month, year, 'Ghost', 10)])
    body = _report(client, user_headers).get_json()
    found = _codes(body)

    assert found['future_date']['blocking'] is True
    assert found['unknown_nick']['blocking'] is False
    assert found['unknown_nick']['examples'][0]['nick'] == 'Ghost'


def test_a_negative_correction_is_refused_and_nothing_changes(app, client, treasurer_headers):
    year, month = _today_pair()
    _seed(app, members=['Alpha'], operations=[(5, month, year, 'Alpha', 10)])
    op_id = _op_id(app)

    resp = client.put(
        f'/api/clan/{CLAN}/treasury/{op_id}',
        json={'quantity': -50},
        headers=treasurer_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'negative_quantity'

    with app.app_context():
        assert db.session.get(TreasuryOperation, op_id).quantity == 10


def test_a_non_numeric_correction_is_refused(app, client, treasurer_headers):
    year, month = _today_pair()
    _seed(app, members=['Alpha'], operations=[(5, month, year, 'Alpha', 10)])
    resp = client.put(
        f'/api/clan/{CLAN}/treasury/{_op_id(app)}',
        json={'quantity': 'много'},
        headers=treasurer_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'bad_quantity'


def test_import_skips_a_negative_row_and_keeps_the_rest(app, client, admin_headers):
    year, month = _today_pair()
    _seed(app, members=['Alpha'])
    resp = client.post(
        f'/api/clan/{CLAN}/treasury/import',
        json={
            'operations': [
                {
                    'date': f'05.{month:02d}.{year} 12:00',
                    'nick': 'Alpha',
                    'operation_type': 'Деньги',
                    'object_name': 'Монеты',
                    'quantity': 10,
                },
                {
                    'date': f'06.{month:02d}.{year} 12:00',
                    'nick': 'Alpha',
                    'operation_type': 'Деньги',
                    'object_name': 'Монеты',
                    'quantity': -500,
                },
            ]
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['imported'] == 1
    assert body['skipped'] == 1
    reasons = json.dumps(body.get('skip_reasons', []), ensure_ascii=False)
    assert 'отрицательная сумма' in reasons

    with app.app_context():
        rows = TreasuryOperation.query.filter_by(clan_id=CLAN).all()
        assert [row.quantity for row in rows] == [10]


def test_import_skips_a_future_dated_row(app, client, admin_headers):
    day, month, year = _future_date()
    _seed(app, members=['Alpha'])
    resp = client.post(
        f'/api/clan/{CLAN}/treasury/import',
        json={
            'operations': [
                {
                    'date': f'{day:02d}.{month:02d}.{year} 12:00',
                    'nick': 'Alpha',
                    'operation_type': 'Деньги',
                    'object_name': 'Монеты',
                    'quantity': 10,
                }
            ]
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['imported'] == 0
    assert 'дата в будущем' in json.dumps(body.get('skip_reasons', []), ensure_ascii=False)
