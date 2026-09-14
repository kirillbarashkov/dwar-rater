"""Clan import hardening (bug: 500 on «Состав клана» → Импортировать).

Scraped values can exceed DB column widths; commit then raised DataError
(StringDataRightTruncation) outside the per-item try and surfaced as HTTP 500.
Imports must clip to the schema and never 500.
"""
from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    ClanMembershipEvent,
    TreasuryOperation,
)

CLAN = 2315


def _seed_clan(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name='TestClan'))
            db.session.commit()


def test_diff_import_clips_overlong_fields(app, client, admin_headers):
    _seed_clan(app)
    long = 'X' * 150
    r = client.post(
        f'/api/clan/{CLAN}/members/diff-import',
        headers=admin_headers,
        json={
            'joined': [{
                'nick': '__Long__', 'level': 5, 'game_rank': long, 'profession': long,
                'profession_level': 2, 'clan_role': long, 'icon': 'I' * 30,
                'join_date': '01.09.2026', 'trial_until': '',
            }],
            'left': [],
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        m = ClanMemberInfo.query.filter_by(clan_id=CLAN, nick='__Long__').first()
        assert m is not None
        assert len(m.game_rank) == 100
        assert len(m.clan_role) == 100
        assert len(m.profession) == 100
        assert len(m.icon) == 10
        assert m.level == 5


def test_diff_import_rejoin_resurrects_without_duplicate(app, client, admin_headers):
    _seed_clan(app)
    with app.app_context():
        db.session.add(ClanMemberInfo(
            clan_id=CLAN, nick='__Rejoin__', level=3, is_deleted=True,
            left_date='01.08.2026',
        ))
        db.session.commit()

    r = client.post(
        f'/api/clan/{CLAN}/members/diff-import',
        headers=admin_headers,
        json={'joined': [{'nick': '__Rejoin__', 'level': 4}], 'left': []},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['joined_count'] == 1
    with app.app_context():
        rows = ClanMemberInfo.query.filter_by(clan_id=CLAN, nick='__Rejoin__').all()
        assert len(rows) == 1, 're-join must not create a duplicate row'
        assert rows[0].is_deleted is False
        assert rows[0].left_date == ''


def test_history_import_clips_long_leave_reason(app, client, admin_headers):
    _seed_clan(app)
    r = client.post(
        f'/api/clan/{CLAN}/members/history-import',
        headers=admin_headers,
        json={'events': [{
            'nick': '__Hist__', 'event_type': 'left', 'event_date': '02.09.2026',
            'leave_reason': 'R' * 250,
        }]},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        ev = ClanMembershipEvent.query.filter_by(clan_id=CLAN, nick='__Hist__').first()
        assert ev is not None
        assert len(ev.leave_reason) == 200


def test_treasury_import_clips_overlong_object_name(app, client, admin_headers):
    _seed_clan(app)
    r = client.post(
        f'/api/clan/{CLAN}/treasury/import',
        headers=admin_headers,
        json={'operations': [{
            'date': '01.09.2026 10:00', 'nick': '__T__', 'operation_type': 'Деньги',
            'object_name': 'M' * 300, 'quantity': 5,
        }]},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        op = TreasuryOperation.query.filter_by(clan_id=CLAN, nick='__T__').first()
        assert op is not None
        assert len(op.object_name) == 200