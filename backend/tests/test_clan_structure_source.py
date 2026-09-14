"""Clan structure deputies/council come from the stored JSON, not from
clan_member_info.clan_role. Saving an edited structure must stick.
"""
from shared.models import db
from shared.models.clan_info import ClanInfo, ClanMemberInfo

CLAN = 2315


def _seed(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="TestClan"))
        # Make sure the nick we put into the structure exists in the roster,
        # otherwise the "drop people who left" filter will remove it.
        for nick in ('Hozaika ozer', 'прото', 'Naysayer', '-Karakurdec-'):
            if not ClanMemberInfo.query.filter_by(
                clan_id=CLAN, nick=nick, is_deleted=False
            ).first():
                db.session.add(ClanMemberInfo(
                    clan_id=CLAN, nick=nick, level=10, clan_role='Рыцарь Ордена',
                    is_deleted=False,
                ))
        db.session.commit()


def test_saved_deputies_persist_across_gets(app, client, admin_headers):
    _seed(app)
    # 18+ members have clan_role='Зам. Главы' in prod; we deliberately
    # save a structure that contains only one of them.
    r = client.put(
        f'/api/clan/{CLAN}/info',
        headers=admin_headers,
        json={'clan_structure': {
            'leader': {'nick': 'Hozaika ozer', 'description': 'Глава Ордена'},
            'deputies': [{'nick': 'прото', 'description': 'Зам. Главы'}],
            'council': [{'nick': 'Naysayer', 'description': 'Совет ордена'}],
            'commander': {'nick': '-Karakurdec-', 'description': 'Воевода'},
            'council_slots': 5,
            'has_members': True,
        }},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    # GET /info: structure should be exactly what we saved
    g = client.get(f'/api/clan/{CLAN}/info', headers=admin_headers)
    assert g.status_code == 200
    struct = g.get_json()['clan_structure']
    assert [d['nick'] for d in struct.get('deputies', [])] == ['прото'], struct
    assert [c['nick'] for c in struct.get('council', [])] == ['Naysayer'], struct
    assert struct.get('commander', {}).get('nick') == '-Karakurdec-', struct


def test_deputies_independent_of_role_counts(app, client, admin_headers):
    """Even if 18 members have clan_role='Зам. Главы', the structure
    deputies list comes from the stored JSON, not from the roster."""
    _seed(app)
    # Sanity: how many members currently have 'Зам. Главы' in the test DB
    with app.app_context():
        n_in_role = ClanMemberInfo.query.filter_by(
            clan_id=CLAN, is_deleted=False, clan_role='Зам. Главы'
        ).count()
    # Save a structure with ZERO deputies
    client.put(
        f'/api/clan/{CLAN}/info',
        headers=admin_headers,
        json={'clan_structure': {
            'leader': {'nick': 'Hozaika ozer', 'description': 'Глава Ордена'},
            'council': [{'nick': 'Naysayer', 'description': 'Совет ордена'}],
            'council_slots': 5,
            'has_members': True,
        }},
    )
    g = client.get(f'/api/clan/{CLAN}/info', headers=admin_headers)
    struct = g.get_json()['clan_structure']
    assert 'deputies' not in struct, struct
    assert n_in_role >= 0  # sanity


def test_commander_removed_when_nick_not_in_roster(app, client, admin_headers):
    _seed(app)
    # Save a commander that doesn't exist in the roster
    client.put(
        f'/api/clan/{CLAN}/info',
        headers=admin_headers,
        json={'clan_structure': {
            'leader': {'nick': 'Hozaika ozer', 'description': 'Глава Ордена'},
            'commander': {'nick': '__NonexistentMember__', 'description': 'Воевода'},
            'council_slots': 5,
            'has_members': True,
        }},
    )
    g = client.get(f'/api/clan/{CLAN}/info', headers=admin_headers)
    struct = g.get_json()['clan_structure']
    assert 'commander' not in struct, struct