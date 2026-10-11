"""GET /treasury/totals: итоги по участнику за всё время.

Вкладке персонажа нужна «Сводка за всё время», а тянуть ради двух чисел всю историю
клана (15 000+ строк ≈ 3,5 МБ) незачем. Эндпоинт отдаёт суммы, сгруппированные по типу
операции и объекту: правила «что налог, а что ресурс» остаются во фронте одним
экземпляром (в tax_engine.py прямо написано, что дублировать список ресурсов нельзя).
"""
from shared.models import db
from shared.models.clan_info import ClanInfo, TreasuryOperation

CLAN = 987303  # выделенный id, не делится с другими тестовыми модулями


def _seed(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name='TotalsClan'))
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        rows = [
            ('10.01.2026 10:00', 'Alpha', 'Деньги', 'Монеты', 100),
            ('10.02.2026 10:00', 'Alpha', 'Деньги', 'Монеты', 50),
            ('11.01.2026 10:00', 'alpha', 'Деньги', 'Монеты', 25),  # другой регистр ника
            ('12.01.2026 10:00', 'Alpha', 'Склад', 'Кристаллы истины', 7),
            ('13.01.2026 10:00', 'Alpha', 'Деньги', 'Монеты', -30),  # списание не считается
            ('14.01.2026 10:00', 'Beta', 'Деньги', 'Монеты', 999),  # другой участник
        ]
        for date, nick, otype, obj, qty in rows:
            db.session.add(TreasuryOperation(
                clan_id=CLAN,
                date=date,
                nick=nick,
                operation_type=otype,
                object_name=obj,
                quantity=qty,
            ))
        db.session.commit()


def test_totals_sum_by_type_and_object_for_one_nick(app, client, admin_headers):
    _seed(app)
    r = client.get(f'/api/clan/{CLAN}/treasury/totals?nick=Alpha', headers=admin_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    groups = {
        (g['operation_type'], g['object_name']): g['total']
        for g in r.get_json()['groups']
    }
    # 100 + 50 + 25 (регистр ника не важен), списание -30 в итоги не идёт
    assert groups[('Деньги', 'Монеты')] == 175
    assert groups[('Склад', 'Кристаллы истины')] == 7
    # Чужой участник не подмешался
    assert sum(groups.values()) == 182


def test_totals_require_a_nick(app, client, admin_headers):
    _seed(app)
    r = client.get(f'/api/clan/{CLAN}/treasury/totals', headers=admin_headers)
    assert r.status_code == 400
