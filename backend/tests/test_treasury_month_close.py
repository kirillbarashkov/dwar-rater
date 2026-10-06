"""API tests for «закрытие месяца» (freezing a settled treasury month).

A closed month is a decision, not a calendar fact: manual writes into it must be
refused until an explicit reopen, and both decisions belong in the journal.
Months are pinned to 2020 so the suite never depends on the wall clock (the one
exception deliberately targets the running month).

The conftest cleanup is a silent no-op, so every test wipes its own clan.
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

CLAN = 987204


def _seed(app, members=(), operations=()):
    with app.app_context():
        AuditLog.query.filter_by(clan_id=CLAN).delete()
        TreasuryMonthClose.query.filter_by(clan_id=CLAN).delete()
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='MonthCloseClan'))
        for nick, level, is_deleted in members:
            db.session.add(
                ClanMemberInfo(
                    clan_id=CLAN, nick=nick, level=level, is_deleted=is_deleted
                )
            )
        for day, month, year, nick, quantity, flagged in operations:
            db.session.add(
                TreasuryOperation(
                    clan_id=CLAN,
                    date=f'{day:02d}.{month:02d}.{year} 12:00',
                    nick=nick,
                    operation_type='Деньги',
                    object_name='Монеты',
                    quantity=quantity,
                    compensation_flag=flagged,
                )
            )
        db.session.commit()


def _op_id(app):
    with app.app_context():
        return TreasuryOperation.query.filter_by(clan_id=CLAN).first().id


def _close(client, headers, year=2020, month=1, **body):
    return client.post(
        f'/api/clan/{CLAN}/treasury/months/{year}/{month}/close',
        json=body,
        headers=headers,
    )


def _reopen(client, headers, year=2020, month=1, **body):
    return client.post(
        f'/api/clan/{CLAN}/treasury/months/{year}/{month}/reopen',
        json=body,
        headers=headers,
    )


BASIC = {'members': [('Alpha', 5, False)],
         'operations': [(10, 1, 2020, 'Alpha', 10, False)]}


def test_close_requires_auth(app, client):
    _seed(app, **BASIC)
    assert _close(client, None).status_code == 401


def test_close_is_denied_for_a_plain_user(app, client, user_headers):
    """Freezing a month is a treasurer decision, not a read-level action."""
    _seed(app, **BASIC)
    assert _close(client, user_headers).status_code == 403


def test_close_refuses_the_running_month(app, client, treasurer_headers):
    _seed(app, **BASIC)
    today = date.today()
    resp = _close(client, treasurer_headers, year=today.year, month=today.month)
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'month_running'


def test_close_marks_the_month_and_audits_it(app, client, treasurer_headers):
    _seed(app, **BASIC)
    resp = _close(client, treasurer_headers, note='свод закрыт')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['closed']['month'] == 1 and body['closed']['year'] == 2020
    assert body['closed']['note'] == 'свод закрыт'
    assert 'proposals' in body

    listing = client.get(f'/api/clan/{CLAN}/treasury/months', headers=treasurer_headers)
    assert listing.status_code == 200
    months = listing.get_json()['months']
    assert [(m['month'], m['year']) for m in months] == [(1, 2020)]

    with app.app_context():
        entry = AuditLog.query.filter_by(clan_id=CLAN, action='treasury_month_close').first()
        assert entry is not None
        assert json.loads(entry.new_value)['month'] == 1

    journal = client.get(f'/api/clan/{CLAN}/treasury/journal', headers=treasurer_headers)
    assert 'treasury_month_close' in json.dumps(journal.get_json(), ensure_ascii=False)


def test_close_is_refused_when_the_month_is_already_closed(app, client, treasurer_headers):
    _seed(app, **BASIC)
    assert _close(client, treasurer_headers).status_code == 200
    second = _close(client, treasurer_headers)
    assert second.status_code == 409
    assert second.get_json()['error'] == 'already_closed'


def test_closed_month_refuses_a_correction(app, client, treasurer_headers):
    """The point of the freeze: a settled month cannot be re-shaken."""
    _seed(app, **BASIC)
    op_id = _op_id(app)
    assert _close(client, treasurer_headers).status_code == 200

    resp = client.put(
        f'/api/clan/{CLAN}/treasury/{op_id}',
        json={'quantity': 777, 'reason': 'import_fix'},
        headers=treasurer_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'month_closed'

    with app.app_context():
        assert db.session.get(TreasuryOperation, op_id).quantity == 10  # untouched


def test_closed_month_refuses_a_reassign(app, client, treasurer_headers):
    _seed(
        app,
        members=[('Alpha', 5, False), ('Beta', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 10, False)],
    )
    op_id = _op_id(app)
    assert _close(client, treasurer_headers).status_code == 200

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/{op_id}/reassign',
        json={'to_nick': 'Beta', 'reason': 'wrong_nick'},
        headers=treasurer_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'month_closed'


def test_reopen_lets_writes_through_again(app, client, treasurer_headers):
    _seed(app, **BASIC)
    op_id = _op_id(app)
    assert _close(client, treasurer_headers).status_code == 200

    resp = _reopen(client, treasurer_headers, reason='other')
    assert resp.status_code == 200

    corrected = client.put(
        f'/api/clan/{CLAN}/treasury/{op_id}',
        json={'quantity': 777, 'reason': 'import_fix'},
        headers=treasurer_headers,
    )
    assert corrected.status_code == 200

    with app.app_context():
        assert db.session.get(TreasuryOperation, op_id).quantity == 777
        assert TreasuryMonthClose.query.filter_by(clan_id=CLAN).count() == 0
        assert (
            AuditLog.query.filter_by(clan_id=CLAN, action='treasury_month_reopen').first()
            is not None
        )


def test_reopen_refuses_a_month_that_was_never_closed(app, client, treasurer_headers):
    _seed(app, **BASIC)
    resp = _reopen(client, treasurer_headers)
    assert resp.status_code == 404
    assert resp.get_json()['error'] == 'not_closed'


def test_closed_month_refuses_a_bulk_import(app, client, treasurer_headers, admin_headers):
    """The freeze must hold for bulk writes — and before the replace wipes data.

    The import needs treasury:admin, and `replace` deletes every operation of the
    clan first, so a refused batch has to be refused while the data is intact.
    """
    _seed(app, **BASIC)
    assert _close(client, treasurer_headers).status_code == 200

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/import',
        json={
            'operations': [
                {
                    'date': '15.01.2020 12:00',
                    'nick': 'Alpha',
                    'operation_type': 'Деньги',
                    'object_name': 'Монеты',
                    'quantity': 999,
                }
            ],
            'replace': True,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'month_closed'

    with app.app_context():
        # The refused replace left the settled month alone.
        rows = TreasuryOperation.query.filter_by(clan_id=CLAN).all()
        assert len(rows) == 1
        assert rows[0].quantity == 10


def test_import_into_an_open_month_still_works(app, client, treasurer_headers, admin_headers):
    _seed(app, **BASIC)
    assert _close(client, treasurer_headers).status_code == 200

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/import',
        json={
            'operations': [
                {
                    'date': '15.02.2020 12:00',
                    'nick': 'Alpha',
                    'operation_type': 'Деньги',
                    'object_name': 'Монеты',
                    'quantity': 50,
                }
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200

