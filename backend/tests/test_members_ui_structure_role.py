"""GET /members exposes ui_structure_role as a separate attribute.

Two role concepts are kept apart:
  - clan_role          — in-game rank imported from dwar.ru
  - ui_structure_role  — role assigned by the user in "Структура клана"
                         (None for members who are not in the structure)

The UI prefers ui_structure_role and falls back to clan_role.
"""
from shared.models import db
from shared.models.clan_info import ClanInfo, ClanMemberInfo

CLAN = 2315


def _seed(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="TestClan"))
        for nick, role in (
            ('Hozaika ozer', 'Глава Ордена'),
            ('прото', 'Зам. Главы'),
            ('Naysayer', 'Совет ордена'),
            ('RangerMember', 'Рыцарь Ордена'),
        ):
            if not ClanMemberInfo.query.filter_by(
                clan_id=CLAN, nick=nick, is_deleted=False
            ).first():
                db.session.add(ClanMemberInfo(
                    clan_id=CLAN, nick=nick, level=10, clan_role=role,
                    is_deleted=False,
                ))
        db.session.commit()


def test_ui_structure_role_is_separate_from_clan_role(app, client, admin_headers):
    _seed(app)
    # The structure moves 'прото' into Совет ордена while the imported
    # clan_role still says 'Зам. Главы' — both must survive untouched.
    client.put(
        f'/api/clan/{CLAN}/info',
        headers=admin_headers,
        json={'clan_structure': {
            'leader': {'nick': 'Hozaika ozer', 'description': 'Глава Ордена'},
            'deputies': [],
            'council': [{'nick': 'прото', 'description': 'Совет ордена'}],
            'council_slots': 1,
        }},
    )
    r = client.get(f'/api/clan/{CLAN}/members', headers=admin_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    by_nick = {m['nick']: m for m in r.get_json()}

    # imported role untouched
    assert by_nick['прото']['clan_role'] == 'Зам. Главы'
    # structural role carried as a separate attribute
    assert by_nick['прото']['ui_structure_role'] == 'Совет ордена'
    assert by_nick['Hozaika ozer']['ui_structure_role'] == 'Глава Ордена'
    # member outside the structure -> None, UI falls back to clan_role
    assert by_nick['RangerMember']['ui_structure_role'] is None
    assert by_nick['RangerMember']['clan_role'] == 'Рыцарь Ордена'


def test_ui_structure_role_none_without_structure(app, client, admin_headers):
    _seed(app)
    with app.app_context():
        ci = ClanInfo.query.filter_by(clan_id=CLAN).first()
        ci.clan_structure = None
        db.session.commit()
    r = client.get(f'/api/clan/{CLAN}/members', headers=admin_headers)
    by_nick = {m['nick']: m for m in r.get_json()}
    assert by_nick['прото']['ui_structure_role'] is None
    assert by_nick['прото']['clan_role'] == 'Зам. Главы'


def test_ui_structure_role_is_case_insensitive(app, client, admin_headers):
    _seed(app)
    client.put(
        f'/api/clan/{CLAN}/info',
        headers=admin_headers,
        json={'clan_structure': {
            'deputies': [{'nick': 'PROTO', 'description': 'Зам. Главы'}],
            'council_slots': 1,
        }},
    )
    r = client.get(f'/api/clan/{CLAN}/members', headers=admin_headers)
    by_nick = {m['nick']: m for m in r.get_json()}
    assert by_nick['прото']['ui_structure_role'] is None  # different nick
    assert by_nick['RangerMember']['ui_structure_role'] is None
