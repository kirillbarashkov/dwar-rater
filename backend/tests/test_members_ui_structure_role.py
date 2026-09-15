"""GET /members exposes ui_structure_role as a separate attribute.

Two role concepts are kept apart:
  - clan_role          — in-game rank imported from dwar.ru
  - ui_structure_role  — role assigned by the user in "Структура клана"
                         (None for members who are not in the structure)

The UI prefers ui_structure_role and falls back to clan_role.

NOTE: these tests use a dedicated clan_id and force the seeded clan_role
values, so they do not depend on rows created by other test modules.
"""
from shared.models import db
from shared.models.clan_info import ClanInfo, ClanMemberInfo

CLAN = 987001  # dedicated id, not shared with other test modules

SEEDED = (
    ('HermeticLeader', 'Глава Ордена'),
    ('HermeticDeputy', 'Зам. Главы'),
    ('HermeticRanger', 'Рыцарь Ордена'),
)


def _seed(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="HermeticClan"))
        for nick, role in SEEDED:
            row = ClanMemberInfo.query.filter_by(
                clan_id=CLAN, nick=nick, is_deleted=False
            ).first()
            if row is None:
                db.session.add(ClanMemberInfo(
                    clan_id=CLAN, nick=nick, level=10, clan_role=role,
                    is_deleted=False,
                ))
            else:
                row.clan_role = role
        db.session.commit()


def _put_structure(client, admin_headers, structure):
    r = client.put(
        f'/api/clan/{CLAN}/info',
        headers=admin_headers,
        json={'clan_structure': structure},
    )
    assert r.status_code == 200, r.get_data(as_text=True)


def _members(client, admin_headers):
    r = client.get(f'/api/clan/{CLAN}/members', headers=admin_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    return {m['nick']: m for m in r.get_json()}


def test_ui_structure_role_is_separate_from_clan_role(app, client, admin_headers):
    _seed(app)
    # Structure puts the deputy into the council; the imported clan_role
    # must stay untouched and travel as its own field.
    _put_structure(client, admin_headers, {
        'leader': {'nick': 'HermeticLeader', 'description': 'Глава Ордена'},
        'deputies': [],
        'council': [{'nick': 'HermeticDeputy', 'description': 'Совет ордена'}],
        'council_slots': 1,
    })
    by_nick = _members(client, admin_headers)

    assert by_nick['HermeticDeputy']['clan_role'] == 'Зам. Главы'
    assert by_nick['HermeticDeputy']['ui_structure_role'] == 'Совет ордена'
    assert by_nick['HermeticLeader']['ui_structure_role'] == 'Глава Ордена'
    # member outside the structure -> None, UI falls back to clan_role
    assert by_nick['HermeticRanger']['ui_structure_role'] is None
    assert by_nick['HermeticRanger']['clan_role'] == 'Рыцарь Ордена'


def test_ui_structure_role_none_without_structure(app, client, admin_headers):
    _seed(app)
    with app.app_context():
        ci = ClanInfo.query.filter_by(clan_id=CLAN).first()
        ci.clan_structure = None
        db.session.commit()
    by_nick = _members(client, admin_headers)
    assert by_nick['HermeticDeputy']['ui_structure_role'] is None
    assert by_nick['HermeticDeputy']['clan_role'] == 'Зам. Главы'


def test_ui_structure_role_nick_matching_is_case_insensitive(app, client, admin_headers):
    _seed(app)
    # Nick cased differently in the structure than in the roster.
    _put_structure(client, admin_headers, {
        'deputies': [{'nick': 'hermeticdeputy', 'description': 'Зам. Главы'}],
        'council_slots': 1,
    })
    by_nick = _members(client, admin_headers)
    assert by_nick['HermeticDeputy']['ui_structure_role'] == 'Зам. Главы'
    # and a member listed in the structure under a different nick stays None
    assert by_nick['HermeticRanger']['ui_structure_role'] is None
