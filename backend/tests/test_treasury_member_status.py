"""Статус участника: налог, ресурсы, обмены, история."""

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    TreasuryOperation,
    TreasuryOperationPair,
)

CLAN = 987007  # dedicated id, not shared with other test modules


def _seed(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name='StatusClan'))
            db.session.commit()

        if not ClanMemberInfo.query.filter_by(clan_id=CLAN, nick='__StatusProbe__').first():
            db.session.add(
                ClanMemberInfo(
                    clan_id=CLAN,
                    nick='__StatusProbe__',
                    level=10,
                    join_date='01.01.2026',
                )
            )
            db.session.commit()

        ops = [
            TreasuryOperation(
                clan_id=CLAN,
                date='05.10.2026 12:00',
                nick='__StatusProbe__',
                operation_type='Деньги',
                object_name='Монеты',
                quantity=100,
                op_class='tax',
            ),
            TreasuryOperation(
                clan_id=CLAN,
                date='06.10.2026 12:00',
                nick='__StatusProbe__',
                operation_type='Предмет',
                object_name='Альва благонравная',
                quantity=4,
                op_class='tax',
            ),
            TreasuryOperation(
                clan_id=CLAN,
                date='07.10.2026 12:00',
                nick='__StatusProbe__',
                operation_type='Предмет',
                object_name='Альва благонравная',
                quantity=9,
                op_class='neutral',
            ),
        ]
        db.session.add_all(ops)
        db.session.commit()

        db.session.add(
            TreasuryOperationPair(
                clan_id=CLAN,
                first_op_id=ops[0].id,
                second_op_id=ops[2].id,
                kind='exchange',
                status='confirmed',
            )
        )
        db.session.commit()


def _status(client, admin_headers):
    resp = client.get(
        f"/api/clan/{CLAN}/treasury/member-status"
        f"?nick=__StatusProbe__&month=10&year=2026",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def test_status_returns_tax_resources_and_pairs(client, admin_headers, app):
    _seed(app)
    data = _status(client, admin_headers)

    assert data['nick'] == '__StatusProbe__'
    assert data['tax']['paid'] == 100
    # Норма зависит от уровня: для 10-го это 20 монет в месяц.
    assert data['tax']['norm'] == 20

    alva = [r for r in data['resources'] if r['object_name'] == 'Альва благонравная']
    assert alva and alva[0]['total'] == 4, 'нейтральная операция не должна попасть в ресурсы'

    assert len(data['pairs']['confirmed']) == 1
    assert len(data['history']) == 3


def test_status_requires_nick(client, admin_headers):
    resp = client.get(f"/api/clan/{CLAN}/treasury/member-status", headers=admin_headers)
    assert resp.status_code == 400
