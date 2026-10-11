"""GET /treasury: необязательный фильтр периода.

Вкладка аналитики работает по одному месяцу, а эндпоинт исторически отдавал всю
историю (15 000+ строк ≈ 3,5 МБ, при том что за месяц их 526–2 256). Фильтр добавлен
опцией: без параметров поведение прежнее, потому что импорт, «Казна» и вкладка
персонажа (там «Сводка за всё время») зовут этот же эндпоинт и им нужна вся история.
"""
from shared.models import db
from shared.models.clan_info import ClanInfo, TreasuryOperation

CLAN = 987302  # выделенный id, не делится с другими тестовыми модулями


def _seed(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name='PeriodClan'))
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        for date, nick in (
            ('15.01.2026 10:00', 'Alpha'),
            ('20.01.2026 12:00', 'Beta'),
            ('03.02.2026 09:00', 'Alpha'),
        ):
            db.session.add(TreasuryOperation(
                clan_id=CLAN,
                date=date,
                nick=nick,
                operation_type='Деньги',
                object_name='Монеты',
                quantity=100,
            ))
        db.session.commit()


def test_month_filter_returns_only_that_month(app, client, admin_headers):
    _seed(app)
    r = client.get(f'/api/clan/{CLAN}/treasury?month=1&year=2026', headers=admin_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    rows = r.get_json()
    assert len(rows) == 2
    assert all('.01.2026' in row['date'] for row in rows)


def test_without_period_the_whole_history_is_returned(app, client, admin_headers):
    """Импорт, «Казна» и вкладка персонажа зовут эндпоинт без параметров."""
    _seed(app)
    rows = client.get(f'/api/clan/{CLAN}/treasury', headers=admin_headers).get_json()
    assert len(rows) == 3


def test_partial_or_invalid_period_is_rejected(app, client, admin_headers):
    """Полузаданный или негодный период — 400, а не молчаливая выдача всей истории."""
    _seed(app)
    for query in (
        '?month=1',
        '?year=2026',
        '?month=13&year=2026',
        '?month=0&year=2026',
        '?month=abc&year=2026',
        '?month=1&year=1999',
    ):
        r = client.get(f'/api/clan/{CLAN}/treasury{query}', headers=admin_headers)
        assert r.status_code == 400, f'{query} → {r.status_code}'
