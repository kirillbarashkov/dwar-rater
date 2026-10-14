"""Агрегат сдачи ресурсов: нейтральные операции не попадают в суммы."""

from shared.models import db
from shared.models.clan_info import ClanInfo, TreasuryOperation

CLAN = 987006  # dedicated id, not shared with other test modules


def _seed(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name='TotalsClan'))
            db.session.commit()

        db.session.add_all(
            [
                TreasuryOperation(
                    clan_id=CLAN,
                    date='01.10.2026',
                    nick='__TotalsProbe__',
                    operation_type='Предмет',
                    object_name='Альва благонравная',
                    quantity=5,
                    op_class='tax',
                ),
                TreasuryOperation(
                    clan_id=CLAN,
                    date='02.10.2026',
                    nick='__TotalsProbe__',
                    operation_type='Предмет',
                    object_name='Альва благонравная',
                    quantity=3,
                    op_class='neutral',
                ),
            ]
        )
        db.session.commit()


def _totals(client, admin_headers, nick):
    resp = client.get(
        f"/api/clan/{CLAN}/treasury/totals?nick={nick}", headers=admin_headers
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return {group['object_name']: group['total'] for group in resp.get_json()['groups']}


def test_neutral_operation_excluded_from_resource_totals(client, admin_headers, app):
    """Подтверждённый обмен или долг — не сдача ресурсов."""
    _seed(app)
    assert _totals(client, admin_headers, '__TotalsProbe__').get('Альва благонравная') == 5


def test_operations_without_class_still_counted(client, admin_headers, app):
    """У записей, не прошедших классификацию, op_class = 'tax' — считаются как раньше."""
    _seed(app)
    with app.app_context():
        db.session.add(
            TreasuryOperation(
                clan_id=CLAN,
                date='03.10.2026',
                nick='__TotalsProbe2__',
                operation_type='Предмет',
                object_name='Золотая шамса',
                quantity=7,
            )
        )
        db.session.commit()

    assert _totals(client, admin_headers, '__TotalsProbe2__').get('Золотая шамса') == 7
