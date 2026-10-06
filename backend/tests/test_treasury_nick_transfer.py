"""API tests for reconnecting a renamed character's history.

The feature exists because an in-game rename splits one person into a ghost and a
debtor. These tests pin that the whole history moves (operations, carry-over rows,
level events), that the review step writes nothing, and that the refusals that
protect the ledger fire.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanLevelChangeEvent,
    ClanMemberInfo,
    TaxCarryover,
    TreasuryOperation,
)
from shared.rbac.models import AuditLog

CLAN = 987207
OLD = 'OldName'
NEW = 'NewName'


def _seed(app, members=(NEW,), operations=(), carryovers=(), level_events=()):
    with app.app_context():
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        TaxCarryover.query.filter_by(clan_id=CLAN).delete()
        ClanLevelChangeEvent.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='RenameClan'))
        for nick in members:
            db.session.add(ClanMemberInfo(clan_id=CLAN, nick=nick, level=19))
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
        for nick, month, year, amount in carryovers:
            db.session.add(
                TaxCarryover(
                    clan_id=CLAN, nick=nick, source_month=month, source_year=year, amount=amount
                )
            )
        for nick, date, old_level, new_level in level_events:
            db.session.add(
                ClanLevelChangeEvent(
                    clan_id=CLAN, nick=nick, event_date=date, old_level=old_level, new_level=new_level
                )
            )
        db.session.commit()


def _call(client, headers, **body):
    return client.post(f'/api/clan/{CLAN}/treasury/nick-transfer', json=body, headers=headers)


def _payload(**overrides):
    body = {'from_nick': OLD, 'to_nick': NEW, 'reason': 'renamed_nick'}
    body.update(overrides)
    return body


def _nics(app):
    with app.app_context():
        return sorted(row.nick for row in TreasuryOperation.query.filter_by(clan_id=CLAN).all())


def _transfer(client, headers, **overrides):
    return _call(client, headers, **_payload(**overrides))


def test_transfer_requires_auth(app, client):
    _seed(app)
    assert _transfer(client, None).status_code == 401


def test_transfer_needs_treasury_write(app, client, user_headers):
    _seed(app)
    assert _transfer(client, user_headers).status_code == 403


def test_the_review_step_moves_nothing(app, client, treasurer_headers):
    _seed(app, operations=[(5, 9, 2026, OLD, 100)], level_events=[(OLD, '01.09.2026', 18, 19)])

    resp = _transfer(client, treasurer_headers, dry_run=True)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['dry_run'] is True
    assert body['plan']['operations']['count'] == 1
    assert body['plan']['operations']['total_quantity'] == 100
    assert body['plan']['level_events']['count'] == 1
    assert _nics(app) == [OLD]


def test_applying_moves_the_whole_history(app, client, treasurer_headers):
    _seed(
        app,
        operations=[
            (5, 9, 2026, OLD, 100),
            (6, 10, 2026, OLD, 50),
            (7, 10, 2026, 'SomeoneElse', 10),
        ],
        carryovers=[(OLD, 9, 2026, 100)],
        level_events=[(OLD, '01.09.2026', 18, 19), ('SomeoneElse', '01.09.2026', 5, 6)],
    )

    resp = _transfer(client, treasurer_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['applied'] is True
    assert body['from_nick'] == OLD
    assert body['to_nick'] == NEW
    assert (body['operations'], body['carryovers'], body['level_events']) == (2, 1, 1)

    with app.app_context():
        rows = TreasuryOperation.query.filter_by(clan_id=CLAN).all()
        moved = [row for row in rows if row.nick == NEW]
        assert sorted(row.quantity for row in moved) == [50, 100]
        # Only the nick changes: dates and amounts travel with the person.
        assert sorted(row.date for row in moved) == ['05.09.2026 12:00', '06.10.2026 12:00']
        assert [row.nick for row in rows if row.nick == 'SomeoneElse'] == ['SomeoneElse']
        assert TaxCarryover.query.filter_by(clan_id=CLAN, nick=NEW).count() == 1
        assert TaxCarryover.query.filter_by(clan_id=CLAN, nick=OLD).count() == 0
        assert ClanLevelChangeEvent.query.filter_by(clan_id=CLAN, nick=NEW).count() == 1


def test_the_roster_spelling_wins_over_what_was_typed(app, client, treasurer_headers):
    _seed(app, operations=[(5, 9, 2026, OLD, 10)])
    resp = _transfer(client, treasurer_headers, to_nick='newname')
    assert resp.status_code == 200
    assert resp.get_json()['to_nick'] == NEW
    assert _nics(app) == [NEW]


def test_the_old_nick_must_not_be_in_the_roster(app, client, treasurer_headers):
    _seed(app, members=[NEW, OLD], operations=[(5, 9, 2026, OLD, 10)])
    resp = _transfer(client, treasurer_headers)
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'from_in_roster'
    assert _nics(app) == [OLD]


def test_the_target_nick_must_be_in_the_roster(app, client, treasurer_headers):
    _seed(app, members=['SomebodyElse'], operations=[(5, 9, 2026, OLD, 10)])
    resp = _transfer(client, treasurer_headers)
    assert resp.status_code == 400
    assert 'нет в составе' in resp.get_json()['error']
    assert _nics(app) == [OLD]


def test_identical_nicks_are_refused(app, client, treasurer_headers):
    _seed(app, operations=[(5, 9, 2026, OLD, 10)])
    assert _transfer(client, treasurer_headers, to_nick=OLD).status_code == 400


def test_an_unknown_reason_is_refused(app, client, treasurer_headers):
    _seed(app, operations=[(5, 9, 2026, OLD, 10)])
    assert _transfer(client, treasurer_headers, reason='just_because').status_code == 400
    assert _transfer(client, treasurer_headers, reason='').status_code == 400
    assert _nics(app) == [OLD]


def test_a_nick_with_nothing_to_move_is_refused(app, client, treasurer_headers):
    _seed(app, operations=[(5, 9, 2026, 'SomeoneElse', 10)])
    resp = _transfer(client, treasurer_headers)
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'nothing_to_move'


def test_a_carryover_the_target_already_has_is_reported_and_left_alone(app, client, treasurer_headers):
    _seed(
        app,
        operations=[(5, 9, 2026, OLD, 100)],
        carryovers=[(OLD, 9, 2026, 100), (NEW, 9, 2026, 40)],
    )
    resp = _transfer(client, treasurer_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['carryovers'] == 0
    assert body['skipped_carryovers'][0]['reason'] == 'carryover_conflict'

    with app.app_context():
        old_row = TaxCarryover.query.filter_by(clan_id=CLAN, nick=OLD).first()
        new_row = TaxCarryover.query.filter_by(clan_id=CLAN, nick=NEW).first()
    # Nothing merged, nothing deleted: both rows survive with their own amounts.
    assert (old_row.amount, new_row.amount) == (100, 40)
    assert _nics(app) == [NEW]


def test_the_transfer_is_audited_and_lands_in_the_journal(app, client, treasurer_headers):
    _seed(app, operations=[(5, 9, 2026, OLD, 100), (6, 9, 2026, OLD, 10)])
    result = _transfer(client, treasurer_headers).get_json()

    with app.app_context():
        entry = (
            AuditLog.query.filter_by(action='treasury_nick_transfer')
            .filter_by(clan_id=CLAN)
            .first()
        )
        assert entry is not None
        payload = json.loads(entry.new_value)
        assert payload['from_nick'] == OLD
        assert payload['to_nick'] == NEW
        assert payload['operations'] == 2
        assert payload['reason'] == 'renamed_nick'
        assert len(payload['operation_ids']) == 2

    journal = client.get(f'/api/clan/{CLAN}/treasury/journal', headers=treasurer_headers).get_json()
    assert any(row['action'] == 'treasury_nick_transfer' for row in journal['entries'])
    assert result['operations'] == 2
