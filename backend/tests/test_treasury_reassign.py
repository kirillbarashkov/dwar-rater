"""API tests for payment re-attribution (/api/clan/<id>/treasury/<op>/reassign).

A «перераспределение» changes whose account the money sits on, never the money
itself. Months are pinned to 2020 so the suite does not depend on the wall clock.

The conftest cleanup is a silent no-op, so each test wipes the rows of its own
clan (including its audit entries) and uses a dedicated clan id.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    TreasuryOperation,
)
from shared.rbac.models import AuditLog

CLAN = 987203


def _seed(app, members=(), operations=()):
    with app.app_context():
        AuditLog.query.filter_by(clan_id=CLAN).delete()
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='ReassignClan'))
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


def _op_id(app, nick=None):
    with app.app_context():
        query = TreasuryOperation.query.filter_by(clan_id=CLAN)
        if nick:
            query = query.filter_by(nick=nick)
        return query.first().id


def _reassign(client, headers, operation_id, **body):
    return client.post(
        f'/api/clan/{CLAN}/treasury/{operation_id}/reassign', json=body, headers=headers
    )


BASIC = {'members': [('Alpha', 5, False), ('Beta', 5, False)],
         'operations': [(10, 1, 2020, 'Alpha', 10, False)]}


def test_reassign_requires_auth(app, client):
    _seed(app, **BASIC)
    resp = _reassign(client, None, _op_id(app), to_nick='Beta', reason='wrong_nick')
    assert resp.status_code == 401


def test_reassign_denied_for_a_plain_user(app, client, user_headers):
    """Re-attributing money needs treasury:write, not just clan read."""
    _seed(app, **BASIC)
    resp = _reassign(
        client, user_headers, _op_id(app), to_nick='Beta', reason='wrong_nick'
    )
    assert resp.status_code == 403


def test_reassign_moves_the_payment_and_keeps_identity(app, client, treasurer_headers):
    _seed(app, **BASIC)
    op_id = _op_id(app)
    resp = _reassign(client, treasurer_headers, op_id, to_nick='Beta', reason='wrong_nick')
    assert resp.status_code == 200

    body = resp.get_json()
    assert body['nick'] == 'Beta'
    assert body['from_nick'] == 'Alpha'
    assert body['quantity'] == 10          # the money is untouched
    assert body['date'] == '10.01.2020 12:00'
    assert body['operation_type'] == 'Деньги'
    assert body['member_status'] == 'active'

    with app.app_context():
        row = db.session.get(TreasuryOperation, op_id)
        assert row.nick == 'Beta'
        assert row.quantity == 10


def test_reassign_uses_the_roster_spelling(app, client, treasurer_headers):
    """A typed «beta» must not create a second nick next to «Beta»."""
    _seed(app, **BASIC)
    resp = _reassign(client, treasurer_headers, _op_id(app), to_nick='beta', reason='wrong_nick')
    assert resp.status_code == 200
    assert resp.get_json()['nick'] == 'Beta'


def test_reassign_refuses_an_unknown_nick(app, client, treasurer_headers):
    _seed(app, **BASIC)
    resp = _reassign(
        client, treasurer_headers, _op_id(app), to_nick='Никого', reason='wrong_nick'
    )
    assert resp.status_code == 400
    assert 'нет в составе' in resp.get_json()['error']


def test_reassign_refuses_the_same_nick_case_insensitively(app, client, treasurer_headers):
    _seed(app, **BASIC)
    resp = _reassign(client, treasurer_headers, _op_id(app), to_nick='alpha', reason='wrong_nick')
    assert resp.status_code == 400


def test_reassign_requires_a_reason(app, client, treasurer_headers):
    _seed(app, **BASIC)
    resp = _reassign(client, treasurer_headers, _op_id(app), to_nick='Beta')
    assert resp.status_code == 400


def test_reassign_refuses_a_compensation_row(app, client, treasurer_headers):
    """A «зачёт» is a waiver, not money — there is nothing to re-attribute."""
    _seed(
        app,
        members=[('Alpha', 5, False), ('Beta', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 10, True)],
    )
    resp = _reassign(client, treasurer_headers, _op_id(app), to_nick='Beta', reason='wrong_nick')
    assert resp.status_code == 400


def test_reassign_refuses_a_row_without_amount(app, client, treasurer_headers):
    _seed(
        app,
        members=[('Alpha', 5, False), ('Beta', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 0, False)],
    )
    resp = _reassign(client, treasurer_headers, _op_id(app), to_nick='Beta', reason='wrong_nick')
    assert resp.status_code == 400


def test_reassign_is_audited_and_shows_up_in_the_journal(app, client, treasurer_headers):
    _seed(app, **BASIC)
    op_id = _op_id(app)
    _reassign(client, treasurer_headers, op_id, to_nick='Beta', reason='wrong_nick')

    with app.app_context():
        entry = AuditLog.query.filter_by(
            clan_id=CLAN, action='treasury_operation_reassign'
        ).first()
        assert entry is not None
        assert entry.target_id == op_id
        # `reason` lives inside new_value — AuditLog has no own column for it.
        assert json.loads(entry.old_value)['nick'] == 'Alpha'
        new = json.loads(entry.new_value)
        assert new['nick'] == 'Beta'
        assert new['reason'] == 'wrong_nick'

    journal = client.get(f'/api/clan/{CLAN}/treasury/journal', headers=treasurer_headers)
    assert journal.status_code == 200
    assert 'treasury_operation_reassign' in json.dumps(journal.get_json(), ensure_ascii=False)


def test_money_follows_the_new_nick_in_the_ledger(app, client, treasurer_headers):
    """The end-to-end point of the feature: the ledger credits the right member.

    The payment moves to Beta, so Alpha is left owing its norm — money follows
    the new attribution, the amount itself never changes.
    """
    _seed(app, **BASIC)
    _reassign(client, treasurer_headers, _op_id(app), to_nick='Beta', reason='wrong_nick')

    resp = client.get(
        f'/api/clan/{CLAN}/tax-ledger'
        '?from_month=1&from_year=2020&to_month=1&to_year=2020',
        headers=treasurer_headers,
    )
    assert resp.status_code == 200
    rows = {r['nick']: r for r in resp.get_json()['rows']}

    assert rows['Beta']['paid_total'] == 10
    assert rows['Beta']['debt'] == 0
    assert rows['Alpha']['paid_total'] == 0
    assert rows['Alpha']['debt'] == 10


def _journal_entry_id(app, action):
    with app.app_context():
        return (
            AuditLog.query.filter_by(clan_id=CLAN, action=action)
            .order_by(AuditLog.id.desc())
            .first()
            .id
        )


def test_journal_marks_a_reassignment_revertable(app, client, treasurer_headers):
    """A wrong re-attribution must be undoable, like any other correction."""
    _seed(app, **BASIC)
    _reassign(client, treasurer_headers, _op_id(app), to_nick='Beta', reason='wrong_nick')

    journal = client.get(f'/api/clan/{CLAN}/treasury/journal', headers=treasurer_headers)
    entry = journal.get_json()['entries'][0]
    assert entry['action'] == 'treasury_operation_reassign'
    assert entry['revertable'] is True


def test_revert_of_a_reassignment_restores_the_nick(app, client, treasurer_headers):
    _seed(app, **BASIC)
    op_id = _op_id(app)
    _reassign(client, treasurer_headers, op_id, to_nick='Beta', reason='wrong_nick')

    entry_id = _journal_entry_id(app, 'treasury_operation_reassign')
    resp = client.post(
        f'/api/clan/{CLAN}/treasury/journal/{entry_id}/revert',
        json={'reason': 'other'},
        headers=treasurer_headers,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(TreasuryOperation, op_id).nick == 'Alpha'
        revert = AuditLog.query.filter_by(
            clan_id=CLAN, action='treasury_journal_revert'
        ).first()
        assert revert is not None
        # The revert is itself history: it records the move back Beta -> Alpha.
        assert json.loads(revert.old_value)['nick'] == 'Beta'
        assert json.loads(revert.new_value)['nick'] == 'Alpha'
