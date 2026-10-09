"""Muting accepted findings: the pure rule and the API lifecycle.

A ghost nick (a member who left) and a prepayment above the norm are legitimate, so
the report keeps naming them until a treasurer says «это нормально». The decision
lives in the database per clan — not in one browser — and it must remove the
finding from the COUNT as well as from the examples, otherwise the totals lie.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    TreasuryAnomalyMute,
    TreasuryOperation,
)
from shared.rbac.models import AuditLog
from shared.services.treasury_anomalies import detect_anomalies

CLAN = 987209


def _op(op_id, nick, quantity=10):
    return {
        'id': op_id,
        'date': '05.10.2026 12:00',
        'nick': nick,
        'operation_type': 'Деньги',
        'object_name': 'Монеты',
        'quantity': quantity,
        'compensation_flag': False,
    }


def _find(items, code):
    for item in items:
        if item['code'] == code:
            return item
    return None


# --------------------------------------------------------------------------- #
# Pure rule
# --------------------------------------------------------------------------- #


def test_a_muted_category_disappears_with_its_count():
    plain = detect_anomalies([_op(1, 'Ghost'), _op(2, 'Ghost')], [], today=__import__('datetime').date(2026, 10, 6))
    assert _find(plain['items'], 'unknown_nick')['count'] == 2

    muted = detect_anomalies(
        [_op(1, 'Ghost'), _op(2, 'Ghost')], [], today=__import__('datetime').date(2026, 10, 6),
        muted=[('unknown_nick', '')],
    )
    assert _find(muted['items'], 'unknown_nick') is None
    assert muted['total'] == 0


def test_a_muted_nick_leaves_the_other_nicks_alone():
    result = detect_anomalies(
        [_op(1, 'Ghost'), _op(2, 'Ghost'), _op(3, 'Other')],
        [],
        today=__import__('datetime').date(2026, 10, 6),
        muted=[('unknown_nick', 'Ghost')],
    )
    item = _find(result['items'], 'unknown_nick')
    assert item['count'] == 1
    assert item['examples'][0]['nick'] == 'Other'
    assert result['total'] == 1


def test_the_ref_match_ignores_case_and_padding():
    result = detect_anomalies(
        [_op(1, 'Ghost')],
        [],
        today=__import__('datetime').date(2026, 10, 6),
        muted=[('unknown_nick', '  GHOST ')],
    )
    assert result['total'] == 0


def test_muting_one_category_does_not_touch_another():
    result = detect_anomalies(
        [_op(1, 'Ghost', quantity=-5)],
        [],
        today=__import__('datetime').date(2026, 10, 6),
        muted=[('unknown_nick', '')],
    )
    assert _find(result['items'], 'unknown_nick') is None
    assert _find(result['items'], 'negative_quantity')['count'] == 1


# --------------------------------------------------------------------------- #
# API lifecycle
# --------------------------------------------------------------------------- #


def _seed(app, operations=()):
    with app.app_context():
        # The suite shares one database: mutes and audit rows from an earlier test
        # in this file would otherwise silence the findings the next test seeds.
        TreasuryAnomalyMute.query.filter_by(clan_id=CLAN).delete()
        AuditLog.query.filter_by(clan_id=CLAN).delete()
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='MuteClan'))
        db.session.add(ClanMemberInfo(clan_id=CLAN, nick='Alpha', level=19))
        for idx, nick in enumerate(operations):
            db.session.add(
                TreasuryOperation(
                    clan_id=CLAN,
                    date='05.10.2026 12:00',
                    nick=nick,
                    operation_type='Деньги',
                    object_name='Монеты',
                    quantity=10,
                    compensation_flag=False,
                )
            )
        db.session.commit()


def _report(client, headers):
    return client.get(f'/api/clan/{CLAN}/treasury/anomalies', headers=headers)


def _mute(client, headers, **body):
    return client.post(f'/api/clan/{CLAN}/treasury/anomalies/mute', json=body, headers=headers)


def _unmute(client, headers, **body):
    return client.post(f'/api/clan/{CLAN}/treasury/anomalies/unmute', json=body, headers=headers)


def _unknown_count(client, headers):
    body = _report(client, headers).get_json()
    item = _find(body['items'], 'unknown_nick')
    return item['count'] if item else 0


def test_mute_requires_treasury_write(app, client, user_headers):
    _seed(app, operations=['Ghost'])
    assert _mute(client, None, code='unknown_nick').status_code == 401
    assert _mute(client, user_headers, code='unknown_nick').status_code == 403


def test_muting_a_category_removes_it_from_the_report(app, client, treasurer_headers):
    _seed(app, operations=['Ghost', 'Ghost2'])
    assert _unknown_count(client, treasurer_headers) == 2

    resp = _mute(client, treasurer_headers, code='unknown_nick')
    assert resp.status_code == 200
    assert resp.get_json()['muted'] == {'code': 'unknown_nick', 'ref': ''}

    body = _report(client, treasurer_headers).get_json()
    assert _unknown_count(client, treasurer_headers) == 0
    assert body['muted'] == [
        {'code': 'unknown_nick', 'ref': '', 'created_by': body['muted'][0]['created_by'], 'created_at': body['muted'][0]['created_at']}
    ]


def test_muting_a_nick_keeps_the_rest(app, client, treasurer_headers):
    _seed(app, operations=['Ghost', 'Other'])
    assert _mute(client, treasurer_headers, code='unknown_nick', ref='Ghost').status_code == 200
    assert _unknown_count(client, treasurer_headers) == 1

    body = _report(client, treasurer_headers).get_json()
    assert _find(body['items'], 'unknown_nick')['examples'][0]['nick'] == 'Other'


def test_muting_twice_is_not_an_error(app, client, treasurer_headers):
    _seed(app, operations=['Ghost'])
    assert _mute(client, treasurer_headers, code='unknown_nick').status_code == 200
    assert _mute(client, treasurer_headers, code='unknown_nick').status_code == 200

    body = _report(client, treasurer_headers).get_json()
    assert len(body['muted']) == 1


def test_unmuting_brings_the_finding_back(app, client, treasurer_headers):
    _seed(app, operations=['Ghost'])
    _mute(client, treasurer_headers, code='unknown_nick')
    assert _unknown_count(client, treasurer_headers) == 0

    assert _unmute(client, treasurer_headers, code='unknown_nick').status_code == 200
    assert _unknown_count(client, treasurer_headers) == 1
    assert _report(client, treasurer_headers).get_json()['muted'] == []


def test_an_unknown_code_is_refused_with_the_list(app, client, treasurer_headers):
    _seed(app, operations=['Ghost'])
    resp = _mute(client, treasurer_headers, code='whatever')
    assert resp.status_code == 400
    assert 'unknown_nick' in resp.get_json()['codes']
    assert _unknown_count(client, treasurer_headers) == 1


def test_the_decision_is_audited_and_lands_in_the_journal(app, client, treasurer_headers):
    _seed(app, operations=['Ghost'])
    _mute(client, treasurer_headers, code='unknown_nick', ref='Ghost')

    with app.app_context():
        entry = (
            AuditLog.query.filter_by(action='treasury_anomaly_mute')
            .filter_by(clan_id=CLAN)
            .first()
        )
        assert entry is not None
        assert entry.clan_id == CLAN
        payload = json.loads(entry.new_value)
        assert payload['code'] == 'unknown_nick'
        assert payload['ref'] == 'Ghost'

    journal = client.get(
        f'/api/clan/{CLAN}/treasury/journal', headers=treasurer_headers
    ).get_json()
    assert any(row['action'] == 'treasury_anomaly_mute' for row in journal['entries'])
