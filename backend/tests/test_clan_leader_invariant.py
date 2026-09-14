"""Single-leader invariant on membership imports.

A bad import should not be able to mark many members as Глава Ордена;
both POST /members/import and POST /members/diff-import must reject any
batch whose union with the existing active leaders has more than one
distinct nick.
"""
from shared.models import db
from shared.models.clan_info import ClanInfo, ClanMemberInfo

CLAN = 2315


def _seed_leader(app, nick="__TestLeader__"):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="TestClan"))
            db.session.commit()
        # Clear existing leaders so the test is hermetic
        ClanMemberInfo.query.filter_by(
            clan_id=CLAN, is_deleted=False, clan_role="Глава Ордена"
        ).delete(synchronize_session=False)
        db.session.commit()
        db.session.add(ClanMemberInfo(
            clan_id=CLAN, nick=nick, level=10, clan_role="Глава Ордена",
            is_deleted=False,
        ))
        db.session.commit()


def test_diff_import_rejects_second_leader(app, client, admin_headers):
    _seed_leader(app)
    r = client.post(
        f'/api/clan/{CLAN}/members/diff-import',
        headers=admin_headers,
        json={
            'joined': [
                {'nick': '__NewLeader__', 'level': 5, 'clan_role': 'Глава Ордена'},
            ],
            'left': [],
        },
    )
    assert r.status_code == 400, r.get_data(as_text=True)
    body = r.get_json()
    assert body['success'] is False
    assert 'Несколько глав' in body['errors'][0]
    assert '__testleader__' in body['errors'][0]
    assert '__newleader__' in body['errors'][0]


def test_diff_import_accepts_single_new_leader(app, client, admin_headers):
    """If DB has no active leader, importing one Глава is fine."""
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="TestClan"))
        ClanMemberInfo.query.filter_by(
            clan_id=CLAN, is_deleted=False, clan_role="Глава Ордена"
        ).delete(synchronize_session=False)
        db.session.commit()
    r = client.post(
        f'/api/clan/{CLAN}/members/diff-import',
        headers=admin_headers,
        json={
            'joined': [
                {'nick': '__Solo__', 'level': 5, 'clan_role': 'Глава Ордена'},
            ],
            'left': [],
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)


def test_import_clan_members_rejects_multi_leader(app, client, admin_headers):
    _seed_leader(app)
    r = client.post(
        f'/api/clan/{CLAN}/members/import',
        headers=admin_headers,
        json={'members': [
            {'nick': '__NewLeader__', 'level': 5, 'clan_role': 'Глава Ордена'},
        ]},
    )
    assert r.status_code == 400
    body = r.get_json()
    assert 'Несколько глав' in body['errors'][0]


def test_diff_import_non_leader_batch_always_passes(app, client, admin_headers):
    """No Глава in batch and at most one in DB -> any number of joined OK."""
    _seed_leader(app, nick="__TheBoss__")
    r = client.post(
        f'/api/clan/{CLAN}/members/diff-import',
        headers=admin_headers,
        json={
            'joined': [
                {'nick': '__Knight1__', 'level': 1, 'clan_role': 'Рыцарь Ордена'},
                {'nick': '__Knight2__', 'level': 2, 'clan_role': 'Леди Ордена'},
            ],
            'left': [],
        },
    )
    assert r.status_code == 200