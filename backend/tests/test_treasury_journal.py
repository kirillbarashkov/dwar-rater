"""Treasury journal: attribution, reason codes and reversal of corrections.

Hermetic on purpose: conftest's TRUNCATE cleanup is a silent no-op (it lists a
table that does not exist), so this clan's rows are cleared explicitly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import ClanInfo, TreasuryOperation
from shared.rbac.models import AuditLog

CLAN = 987301
OTHER_CLAN = 987302


def _seed(app, clan_id=CLAN):
    """A clan with one treasury operation, and no leftover journal rows."""
    with app.app_context():
        AuditLog.query.filter_by(clan_id=clan_id).delete()
        AuditLog.query.filter_by(clan_id=OTHER_CLAN).delete()
        for cid in (clan_id, OTHER_CLAN):
            TreasuryOperation.query.filter_by(clan_id=cid).delete()
            ClanInfo.query.filter_by(clan_id=cid).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=clan_id, name='JournalClan'))
        db.session.add(ClanInfo(clan_id=OTHER_CLAN, name='OtherClan'))
        db.session.commit()
        for cid in (clan_id, OTHER_CLAN):
            db.session.add(
                TreasuryOperation(
                    clan_id=cid,
                    date='10.01.2020 12:00',
                    nick='Payer',
                    operation_type='Деньги',
                    object_name='Монеты',
                    quantity=10,
                )
            )
        db.session.commit()
        op = TreasuryOperation.query.filter_by(clan_id=clan_id).first()
        other_op = TreasuryOperation.query.filter_by(clan_id=OTHER_CLAN).first()
        return op.id, other_op.id


def _journal(client, headers, clan_id=CLAN, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/api/clan/{clan_id}/treasury/journal" + (f"?{query}" if query else "")
    return client.get(url, headers=headers)


def _edit(client, headers, op_id, clan_id=CLAN, **payload):
    return client.put(
        f"/api/clan/{clan_id}/treasury/{op_id}", json=payload, headers=headers
    )


def test_edit_is_recorded_with_reason(app, client, treasurer_headers):
    op_id, _ = _seed(app)
    resp = _edit(
        client,
        treasurer_headers,
        op_id,
        quantity=250,
        compensation_comment='исправлено',
        reason='wrong_nick',
    )
    assert resp.status_code == 200

    body = _journal(client, treasurer_headers).get_json()
    assert body['total'] == 1
    entry = body['entries'][0]
    assert entry['action'] == 'treasury_operation_update'
    assert entry['nick'] == 'Payer'
    assert entry['reason'] == 'wrong_nick'
    assert entry['old']['quantity'] == 10
    assert entry['new']['quantity'] == 250
    assert entry['username'] == 'testtreasurer'
    assert entry['revertable'] is True


def test_edit_without_reason_stores_none(app, client, treasurer_headers):
    op_id, _ = _seed(app)
    _edit(client, treasurer_headers, op_id, quantity=100)
    entry = _journal(client, treasurer_headers).get_json()['entries'][0]
    assert entry['reason'] is None


def test_journal_is_scoped_to_the_clan(app, client, treasurer_headers):
    op_id, other_op_id = _seed(app)
    _edit(client, treasurer_headers, op_id, quantity=250)
    _edit(client, treasurer_headers, other_op_id, clan_id=OTHER_CLAN, quantity=999)

    mine = _journal(client, treasurer_headers).get_json()
    theirs = _journal(client, treasurer_headers, clan_id=OTHER_CLAN).get_json()
    assert mine['total'] == 1
    assert theirs['total'] == 1
    assert mine['entries'][0]['new']['quantity'] == 250
    assert theirs['entries'][0]['new']['quantity'] == 999


def test_reason_codes_are_served(app, client, treasurer_headers):
    _seed(app)
    body = _journal(client, treasurer_headers).get_json()
    codes = [c['code'] for c in body['reason_codes']]
    assert 'wrong_nick' in codes
    assert 'carryover_credit' in codes
    assert len(codes) == 8
    assert 'treasury_operation_update' in body['actions']


def test_journal_denied_for_plain_user(app, client, user_headers):
    _seed(app)
    assert _journal(client, user_headers).status_code == 403


def test_journal_filter_by_action(app, client, treasurer_headers):
    op_id, _ = _seed(app)
    _edit(client, treasurer_headers, op_id, quantity=250)
    client.post(
        f'/api/clan/{CLAN}/treasury/compensation',
        json={'nick': 'Payer', 'norm_amount': 10, 'months': [2], 'year': 2020},
        headers=treasurer_headers,
    )

    only_edits = _journal(
        client, treasurer_headers, action='treasury_operation_update'
    ).get_json()
    assert only_edits['total'] == 1
    assert only_edits['entries'][0]['action'] == 'treasury_operation_update'


def test_revert_restores_previous_values(app, client, treasurer_headers):
    op_id, _ = _seed(app)
    _edit(client, treasurer_headers, op_id, quantity=250, reason='wrong_nick')
    entry_id = _journal(client, treasurer_headers).get_json()['entries'][0]['id']

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/journal/{entry_id}/revert',
        json={'reason': 'other'},
        headers=treasurer_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['restored']['quantity'] == 10

    with app.app_context():
        op = TreasuryOperation.query.filter_by(id=op_id).first()
        assert op.quantity == 10

    body = _journal(client, treasurer_headers).get_json()
    assert body['total'] == 2
    assert body['entries'][0]['action'] == 'treasury_journal_revert'
    assert body['entries'][0]['new']['quantity'] == 10
    assert body['entries'][0]['nick'] == 'Payer'


def test_revert_refuses_when_operation_changed_later(app, client, treasurer_headers):
    op_id, _ = _seed(app)
    _edit(client, treasurer_headers, op_id, quantity=250, reason='wrong_nick')
    first_entry = _journal(client, treasurer_headers).get_json()['entries'][0]['id']
    # A newer correction lands on the same operation.
    _edit(client, treasurer_headers, op_id, quantity=999, reason='other')

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/journal/{first_entry}/revert',
        json={},
        headers=treasurer_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json()['error'] == 'operation_changed'

    with app.app_context():
        assert TreasuryOperation.query.filter_by(id=op_id).first().quantity == 999


def test_revert_rejects_non_update_entries(app, client, treasurer_headers):
    _seed(app)
    client.post(
        f'/api/clan/{CLAN}/treasury/compensation',
        json={'nick': 'Payer', 'norm_amount': 10, 'months': [2], 'year': 2020},
        headers=treasurer_headers,
    )
    entry_id = _journal(
        client, treasurer_headers, action='treasury_compensation_create'
    ).get_json()['entries'][0]['id']

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/journal/{entry_id}/revert',
        json={},
        headers=treasurer_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'not_revertable'


def test_revert_unknown_entry_is_404(app, client, treasurer_headers):
    _seed(app)
    resp = client.post(
        f'/api/clan/{CLAN}/treasury/journal/999999/revert', json={}, headers=treasurer_headers
    )
    assert resp.status_code == 404


def test_revert_denied_for_plain_user(app, client, user_headers, treasurer_headers):
    op_id, _ = _seed(app)
    _edit(client, treasurer_headers, op_id, quantity=250)
    entry_id = _journal(client, treasurer_headers).get_json()['entries'][0]['id']

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/journal/{entry_id}/revert', json={}, headers=user_headers
    )
    assert resp.status_code == 403


def test_foreign_clan_entry_is_not_revertable(app, client, treasurer_headers):
    """An entry id from another clan must not act on this clan."""
    op_id, _ = _seed(app)
    _edit(client, treasurer_headers, op_id, quantity=250)
    entry_id = _journal(client, treasurer_headers).get_json()['entries'][0]['id']

    resp = client.post(
        f'/api/clan/{OTHER_CLAN}/treasury/journal/{entry_id}/revert',
        json={},
        headers=treasurer_headers,
    )
    assert resp.status_code == 404
