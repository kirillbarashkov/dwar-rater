"""A12: импорт без замены диапазона (append) — путь, который раньше делал N+1.

Пока `authoritative=True` (replace / replace_range), база только что очищена и
поиск существующих строк не нужен. При обычном дозаписывающем импорте
(`authoritative=False`) код раньше делал отдельный SELECT на КАЖДУЮ строку —
при 15k операций это 15k запросов. Теперь существующие строки забираются одним
запросом и ищутся по словарю.

Тесты закрепляют поведение именно этого пути: словарь обязан вести себя как
прежний per-row SELECT, иначе поедет дедупликация казны.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import ClanInfo, TreasuryOperation

CLAN = 987241

OP = {
    "date": "09.09.2026 20:03",
    "nick": "_ Sanych_",
    "operation_type": "Деньги",
    "object_name": "Монеты",
    "quantity": 100,
}


@pytest.fixture(autouse=True)
def _clan(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="AppendClan"))
            db.session.commit()
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()
    yield
    with app.app_context():
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()


def _append(client, headers, operations):
    """Импорт БЕЗ replace/replace_range — ровно тот путь, где был N+1."""
    return client.post(
        f"/api/clan/{CLAN}/treasury/import",
        headers=headers,
        json={"operations": operations, "replace_range": False},
    )


def _rows(app):
    with app.app_context():
        return TreasuryOperation.query.filter_by(clan_id=CLAN).all()


def test_first_append_inserts(app, client, admin_headers):
    resp = _append(client, admin_headers, [OP])
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert len(_rows(app)) == 1


def test_second_append_with_same_key_and_amount_updates(app, client, admin_headers):
    _append(client, admin_headers, [OP])
    resp = _append(client, admin_headers, [OP])
    assert resp.status_code == 200, resp.get_data(as_text=True)

    rows = _rows(app)
    assert len(rows) == 1, f'строка задублировалась: {len(rows)}'


def test_second_append_with_different_amount_adds_a_row(app, client, admin_headers):
    """Двар легитимно повторяет платёж другой суммой — это ОТДЕЛЬНАЯ строка.

    Именно поэтому на таблицу нельзя вешать уникальный ключ по
    (clan_id, date, nick, operation_type, object_name): он отклонил бы вставку.
    """
    _append(client, admin_headers, [OP])
    resp = _append(client, admin_headers, [{**OP, "quantity": 250}])
    assert resp.status_code == 200, resp.get_data(as_text=True)

    rows = _rows(app)
    assert len(rows) == 2, f'ожидалось 2 строки (разные суммы), получено {len(rows)}'
    assert {r.quantity for r in rows} == {100, 250}


def test_append_leaves_other_keys_alone(app, client, admin_headers):
    other = {**OP, "nick": "Другой", "quantity": 7}
    _append(client, admin_headers, [OP])
    resp = _append(client, admin_headers, [other])
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert len(_rows(app)) == 2
