"""TD-6: импорт состава обязан оставлять запись в audit_log.

Без неё нельзя понять, какой импорт занёс мусор в состав: раньше в
`import_clan_members` не было ни одного `_audit`.
"""

import json

from shared.models import db
from shared.models.clan_info import ClanInfo
from shared.rbac.models import AuditLog

CLAN = 987002  # dedicated id, not shared with other test modules


def _seed_clan(app):
    """Импорт пишет состав с FK на clan_info: без клана транзакция падает, а вместе
    с ней откатывается и аудит — он готовится в той же транзакции."""
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="AuditClan"))
            db.session.commit()


def test_members_import_is_audited(app, client, admin_headers):
    _seed_clan(app)

    payload = {
        "members": [{"nick": "__AuditProbe__", "level": 10, "game_rank": "Воин"}],
        "overwrite": False,
    }
    resp = client.post(
        f"/api/clan/{CLAN}/members/import", json=payload, headers=admin_headers
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with app.app_context():
        entries = AuditLog.query.filter_by(
            action="clan_members_import", clan_id=CLAN
        ).all()
        assert len(entries) == 1, "импорт состава должен писать ровно одну запись аудита"

        entry = entries[0]
        assert entry.target_id == CLAN

        value = entry.new_value
        if isinstance(value, str):
            value = json.loads(value)
        assert value is not None
        # Количества и признак перезаписи — иначе запись бесполезна для разбора.
        for key in ("incoming", "overwrite", "success", "skipped", "failed"):
            assert key in value, f"в аудите нет поля {key}"
        assert value["incoming"] == 1
        assert value["success"] == 1
        assert value["overwrite"] is False
