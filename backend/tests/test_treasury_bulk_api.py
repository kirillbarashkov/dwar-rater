"""API tests for bulk tax waivers with a dry-run preview.

The point of the pair is that the preview writes NOTHING and the apply does
exactly what the preview showed — both run the same planner. These tests pin the
first property (row counts unchanged) and the second (identical item set).

Run in the container like the rest of the suite (see the project skill).
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    TreasuryMonthClose,
    TreasuryOperation,
)
from shared.rbac.models import AuditLog

CLAN = 987206


def _seed(app, members=(), operations=(), closes=()):
    with app.app_context():
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        TreasuryMonthClose.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='BulkClan'))
        for nick, level in members:
            db.session.add(ClanMemberInfo(clan_id=CLAN, nick=nick, level=level))
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
        for month, year in closes:
            db.session.add(TreasuryMonthClose(clan_id=CLAN, month=month, year=year))
        db.session.commit()


def _today():
    today = date.today()
    return today.year, today.month


def _next_month():
    year, month = _today()
    month += 1
    if month > 12:
        month = 1
        year += 1
    return year, month


def _count(app, **filters):
    with app.app_context():
        return TreasuryOperation.query.filter_by(clan_id=CLAN, **filters).count()


def _compensations(app):
    with app.app_context():
        return TreasuryOperation.query.filter_by(clan_id=CLAN, compensation_flag=True).all()


def _preview(client, headers, **body):
    return client.post(f'/api/clan/{CLAN}/treasury/compensation/bulk/preview', json=body, headers=headers)


def _apply(client, headers, **body):
    return client.post(f'/api/clan/{CLAN}/treasury/compensation/bulk/apply', json=body, headers=headers)


def test_preview_requires_auth(app, client):
    _seed(app, members=[('Alpha', 19)])
    assert _preview(client, None, nicks=['Alpha'], months=[1], year=2026).status_code == 401


def test_preview_needs_treasury_write(app, client, user_headers):
    _seed(app, members=[('Alpha', 19)])
    assert _preview(client, user_headers, nicks=['Alpha'], months=[1], year=2026).status_code == 403


def test_preview_writes_nothing(app, client, treasurer_headers):
    year, month = _today()
    _seed(app, members=[('Alpha', 19)], operations=[(5, month, year, 'Alpha', 10)])
    before = _count(app)

    resp = _preview(client, treasurer_headers, nicks=['Alpha'], months=[month], year=year)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['totals']['create'] == 1
    assert body['items'][0]['amount'] == 100
    assert _count(app) == before
    assert _compensations(app) == []


def test_preview_classifies_every_pair(app, client, treasurer_headers):
    year, month = _today()
    future_year, future_month = _next_month()
    _seed(
        app,
        members=[('Alpha', 19)],
        operations=[(15, month, year, 'Alpha', 100)],
        closes=[(month, year)],
    )

    body = _preview(
        client,
        treasurer_headers,
        nicks=['Alpha', 'Ghost'],
        months=[month, future_month],
        year=year,
    ).get_json()

    items = {(i['nick'], i['month']): i for i in body['items']}
    # A closed month is a refusal for EVERY nick in it — it outranks both the
    # roster check and the "month has not started" check.
    assert items[('Alpha', month)]['reason'] == 'month_closed'
    assert items[('Ghost', month)]['reason'] == 'month_closed'
    assert items[('Alpha', future_month)]['reason'] == 'future_month'
    assert items[('Ghost', future_month)]['reason'] == 'future_month'
    assert body['totals'] == {'pairs': 4, 'create': 0, 'skip': 0, 'blocked': 4}
    assert body['by_reason'] == {'month_closed': 2, 'future_month': 2}


def test_a_zero_amount_override_is_skipped_as_no_norm(app, client, treasurer_headers):
    year, month = _today()
    _seed(app, members=[('Alpha', 19)])
    body = _preview(
        client, treasurer_headers, nicks=['Alpha'], months=[month], year=year,
        amount_by_nick={'alpha': 0},
    ).get_json()
    assert body['items'][0]['reason'] == 'no_norm'


def test_apply_writes_exactly_what_the_preview_showed(app, client, treasurer_headers):
    year, month = _today()
    _seed(app, members=[('Alpha', 19), ('Beta', 1)])
    payload = dict(nicks=['Alpha', 'Beta', 'Ghost'], months=[month], year=year, comment='Совет')

    planned = _preview(client, treasurer_headers, **payload).get_json()
    ghost = next(i for i in planned['items'] if i['nick'] == 'Ghost')
    assert (ghost['action'], ghost['reason']) == ('skip', 'unknown_nick')

    applied = _apply(client, treasurer_headers, **payload)
    assert applied.status_code == 201
    result = applied.get_json()
    assert result['created'] == planned['totals']['create'] == 2
    assert result['plan']['items'] == planned['items']

    rows = _compensations(app)
    assert sorted((r.nick, r.quantity, r.compensation_flag, r.compensation_comment) for r in rows) == [
        ('Alpha', 100, True, 'Совет'),
        ('Beta', 10, True, 'Совет'),
    ]
    assert [o['id'] for o in result['operations']] == sorted(r.id for r in rows)
    assert all(r.date.startswith(f'15.{month:02d}.{year}') for r in rows)


def test_apply_twice_does_not_duplicate(app, client, treasurer_headers):
    year, month = _today()
    _seed(app, members=[('Alpha', 19)])
    payload = dict(nicks=['Alpha'], months=[month], year=year)

    assert _apply(client, treasurer_headers, **payload).get_json()['created'] == 1
    second = _apply(client, treasurer_headers, **payload)
    assert second.status_code == 201
    assert second.get_json()['created'] == 0
    assert second.get_json()['plan']['items'][0]['reason'] == 'already_compensated'
    assert len(_compensations(app)) == 1


def test_apply_refuses_an_empty_request(app, client, treasurer_headers):
    _seed(app, members=[('Alpha', 19)])
    assert _apply(client, treasurer_headers, nicks=[], months=[]).status_code == 400


def test_apply_on_a_closed_month_creates_nothing(app, client, treasurer_headers):
    year, month = _today()
    _seed(app, members=[('Alpha', 19)], closes=[(month, year)])
    resp = _apply(client, treasurer_headers, nicks=['Alpha'], months=[month], year=year)
    assert resp.status_code == 201
    assert resp.get_json()['created'] == 0
    assert _compensations(app) == []


def test_the_batch_is_audited_and_lands_in_the_journal(app, client, treasurer_headers):
    year, month = _today()
    _seed(app, members=[('Alpha', 19)])
    result = _apply(client, treasurer_headers, nicks=['Alpha'], months=[month], year=year).get_json()

    with app.app_context():
        # Aimed at this batch: a plain .first() by action picks up another test's
        # entry (the suite shares one database).
        entry = (
            AuditLog.query.filter_by(action='treasury_compensation_bulk')
            .filter_by(target_id=result['operations'][0]['id'])
            .first()
        )
        assert entry is not None
        assert entry.clan_id == CLAN
        assert entry.target_id == result['operations'][0]['id']
        payload = json.loads(entry.new_value)
        assert payload['count'] == 1
        assert payload['operations'][0]['nick'] == 'Alpha'

    journal = client.get(f'/api/clan/{CLAN}/treasury/journal', headers=treasurer_headers).get_json()
    assert any(row['action'] == 'treasury_compensation_bulk' for row in journal['entries'])
