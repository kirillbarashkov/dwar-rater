"""API tests for the tax carry-over ledger (/api/clan/<id>/tax-carryover).

Months are pinned to 2020 so the suite never depends on the wall clock, except
the one test that deliberately targets the running month (which must be refused
by recompute and only offered as a preview).
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    TreasuryOperation,
    TaxCarryover,
)
from shared.rbac.models import AuditLog

CLAN = 987201


def _seed_clan(app, members=(), operations=()):
    """Seed clan CLAN from scratch.

    The suite's TRUNCATE-based cleanup in conftest is a silent no-op (it lists
    a table that does not exist, the exception is swallowed), so every test
    sees leftovers from the previous one. Clean this clan's rows explicitly —
    tests must be hermetic rather than order-dependent.
    """
    with app.app_context():
        TaxCarryover.query.filter_by(clan_id=CLAN).delete()
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='CarryClan'))
        for nick, level, is_deleted in members:
            db.session.add(
                ClanMemberInfo(
                    clan_id=CLAN,
                    nick=nick,
                    level=level,
                    is_deleted=is_deleted,
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


def _recompute(client, headers, month, year):
    return client.post(
        f'/api/clan/{CLAN}/tax-carryover/recompute',
        json={'month': month, 'year': year},
        headers=headers,
    )


def _get(client, headers, month, year):
    return client.get(
        f'/api/clan/{CLAN}/tax-carryover?month={month}&year={year}', headers=headers
    )


def _pending_ids(client, headers, month, year):
    body = _get(client, headers, month, year).get_json()
    return [c['id'] for c in body['carryovers'] if c['status'] == 'pending']


def test_recompute_creates_pending_proposal(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    resp = _recompute(client, treasurer_headers, 1, 2020)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body['created'] == 1
    assert body['carryovers'][0]['amount'] == 240
    assert body['carryovers'][0]['status'] == 'pending'


def test_recompute_is_idempotent(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    _recompute(client, treasurer_headers, 1, 2020)
    body = _recompute(client, treasurer_headers, 1, 2020).get_json()
    assert body['created'] == 0
    assert body['updated'] == 0
    assert len(body['carryovers']) == 1

    with app.app_context():
        assert TaxCarryover.query.filter_by(clan_id=CLAN).count() == 1


def test_recompute_rejects_the_running_month(app, client, treasurer_headers):
    today = date.today()
    _seed_clan(app, members=[('Alpha', 5, False)], operations=[])
    resp = _recompute(client, treasurer_headers, today.month, today.year)
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'month_not_closed'


def test_recompute_and_confirm_denied_for_plain_user(app, client, user_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    assert _recompute(client, user_headers, 1, 2020).status_code == 403

    _recompute(client, _admin_headers(app, client), 1, 2020)
    ids = _pending_ids(client, _admin_headers(app, client), 1, 2020)
    resp = client.post(
        f'/api/clan/{CLAN}/tax-carryover/{ids[0]}/confirm', json={}, headers=user_headers
    )
    assert resp.status_code == 403


def test_get_is_open_to_viewers(app, client, user_headers):
    _seed_clan(app, members=[('Alpha', 5, False)], operations=[])
    assert _get(client, user_headers, 1, 2020).status_code == 200


def test_open_month_returns_a_preview_only(app, client, user_headers):
    today = date.today()
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(1, today.month, today.year, 'Alpha', 250, False)],
    )
    body = _get(client, user_headers, today.month, today.year).get_json()
    assert body['is_closed'] is False
    assert body['carryovers'] == []
    assert [p['nick'] for p in body['preview']] == ['Alpha']
    assert body['preview'][0]['amount'] == 240


def test_confirmed_credit_shows_as_incoming_next_month(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    _recompute(client, treasurer_headers, 1, 2020)
    ids = _pending_ids(client, treasurer_headers, 1, 2020)
    resp = client.post(
        f'/api/clan/{CLAN}/tax-carryover/{ids[0]}/confirm',
        json={'comment': 'переносим'},
        headers=treasurer_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()['carryover']['status'] == 'confirmed'

    feb = _get(client, treasurer_headers, 2, 2020).get_json()
    assert feb['incoming'] == [
        {'nick': 'Alpha', 'amount': 240, 'source_month': 1, 'source_year': 2020}
    ]
    assert feb['carryovers'] == []


def test_confirming_twice_conflicts(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    _recompute(client, treasurer_headers, 1, 2020)
    ids = _pending_ids(client, treasurer_headers, 1, 2020)
    url = f'/api/clan/{CLAN}/tax-carryover/{ids[0]}/confirm'
    assert client.post(url, json={}, headers=treasurer_headers).status_code == 200
    second = client.post(url, json={}, headers=treasurer_headers)
    assert second.status_code == 409
    assert second.get_json()['error'] == 'not_pending'


def test_cancelled_proposal_is_not_resurrected(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    _recompute(client, treasurer_headers, 1, 2020)
    ids = _pending_ids(client, treasurer_headers, 1, 2020)
    client.post(
        f'/api/clan/{CLAN}/tax-carryover/{ids[0]}/cancel',
        json={'comment': 'не переносим'},
        headers=treasurer_headers,
    )

    body = _recompute(client, treasurer_headers, 1, 2020).get_json()
    assert len(body['carryovers']) == 1
    assert body['carryovers'][0]['status'] == 'cancelled'


def test_cancelled_previous_month_removes_the_next_credit(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 310, False)],
    )
    _recompute(client, treasurer_headers, 1, 2020)
    assert _pending_ids(client, treasurer_headers, 1, 2020)

    # With January's carry confirmed, February still has a credit.
    ids = _pending_ids(client, treasurer_headers, 1, 2020)
    client.post(
        f'/api/clan/{CLAN}/tax-carryover/{ids[0]}/confirm',
        json={},
        headers=treasurer_headers,
    )
    feb = _recompute(client, treasurer_headers, 2, 2020).get_json()
    assert [c['amount'] for c in feb['carryovers']] == [290]

    # Cancel it instead: February must fall back to no credit at all.
    with app.app_context():
        row = TaxCarryover.query.filter_by(
            clan_id=CLAN, source_month=1, source_year=2020
        ).first()
        row.status = 'cancelled'
        db.session.commit()

    feb_after = _recompute(client, treasurer_headers, 2, 2020).get_json()
    assert feb_after['removed'] == 1
    assert feb_after['carryovers'] == []


def test_departed_member_is_not_proposed(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, True)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    body = _recompute(client, treasurer_headers, 1, 2020).get_json()
    assert body['created'] == 0


def test_bulk_confirm_and_skip(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False), ('Beta', 5, False)],
        operations=[
            (10, 1, 2020, 'Alpha', 250, False),
            (11, 1, 2020, 'Beta', 50, False),
        ],
    )
    _recompute(client, treasurer_headers, 1, 2020)
    ids = _pending_ids(client, treasurer_headers, 1, 2020)
    assert len(ids) == 2

    first = client.post(
        f'/api/clan/{CLAN}/tax-carryover/{ids[0]}/confirm', json={}, headers=treasurer_headers
    )
    assert first.status_code == 200

    body = client.post(
        f'/api/clan/{CLAN}/tax-carryover/bulk',
        json={'ids': ids, 'action': 'confirm'},
        headers=treasurer_headers,
    ).get_json()
    assert body['updated'] == 1
    assert body['skipped_ids'] == [ids[0]]


def test_bulk_rejects_unknown_action(app, client, treasurer_headers):
    _seed_clan(app, members=[('Alpha', 5, False)], operations=[])
    resp = client.post(
        f'/api/clan/{CLAN}/tax-carryover/bulk',
        json={'ids': [1], 'action': 'maybe'},
        headers=treasurer_headers,
    )
    assert resp.status_code == 400


def test_review_is_audited(app, client, treasurer_headers):
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    _recompute(client, treasurer_headers, 1, 2020)
    ids = _pending_ids(client, treasurer_headers, 1, 2020)
    client.post(
        f'/api/clan/{CLAN}/tax-carryover/{ids[0]}/confirm', json={}, headers=treasurer_headers
    )

    with app.app_context():
        actions = {a.action for a in AuditLog.query.all()}
    assert 'tax_carryover_recompute' in actions
    assert 'tax_carryover_confirmed' in actions


def test_confirmed_amount_survives_recompute(app, client, treasurer_headers):
    """A confirmed decision is an input, not a derived row."""
    _seed_clan(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 250, False)],
    )
    _recompute(client, treasurer_headers, 1, 2020)
    ids = _pending_ids(client, treasurer_headers, 1, 2020)
    client.post(
        f'/api/clan/{CLAN}/tax-carryover/{ids[0]}/confirm', json={}, headers=treasurer_headers
    )

    # More money arrives in January after the fact.
    with app.app_context():
        db.session.add(
            TreasuryOperation(
                clan_id=CLAN,
                date='20.01.2020 12:00',
                nick='Alpha',
                operation_type='Деньги',
                object_name='Монеты',
                quantity=100,
                compensation_flag=False,
            )
        )
        db.session.commit()

    body = _recompute(client, treasurer_headers, 1, 2020).get_json()
    assert body['carryovers'][0]['status'] == 'confirmed'
    assert body['carryovers'][0]['amount'] == 240


def _admin_headers(app, client):
    """Admin headers built inline (conftest's admin_headers needs the fixture)."""
    from shared.models.user import User
    import secrets
    from datetime import datetime, timezone, timedelta
    from shared.rbac.models import SessionToken

    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        token = secrets.token_hex(32)
        db.session.add(
            SessionToken(
                user_id=admin.id,
                token_hash=SessionToken.hash_token(token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.session.commit()
    return {'Authorization': f'Bearer {token}'}
