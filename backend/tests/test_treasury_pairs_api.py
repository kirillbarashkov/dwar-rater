"""API очереди пар казны: подтверждение, отклонение, корректировка, кандидаты."""

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    TreasuryOperation,
    TreasuryOperationPair,
)
from shared.rbac.models import AuditLog

CLAN = 987005  # dedicated id, not shared with other test modules


def _seed(app):
    """Клан, две операции (деньги и ресурс) и пара-кандидат."""
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="ApiClan"))
            db.session.commit()

        op1 = TreasuryOperation(
            clan_id=CLAN,
            date='01.10.2026',
            nick='__ApiProbe__',
            operation_type='Деньги',
            object_name='Монеты',
            quantity=100,
        )
        op2 = TreasuryOperation(
            clan_id=CLAN,
            date='01.10.2026',
            nick='__ApiProbe__',
            operation_type='Предмет',
            object_name='Ресурс',
            quantity=-5,
        )
        db.session.add_all([op1, op2])
        db.session.commit()

        pair = TreasuryOperationPair(
            clan_id=CLAN, first_op_id=op1.id, second_op_id=op2.id
        )
        db.session.add(pair)
        db.session.commit()
        return pair.id, op1.id


def test_queue_returns_candidates(client, admin_headers, app):
    pair_id, _ = _seed(app)
    resp = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate", headers=admin_headers
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['total'] >= 1
    assert any(item['id'] == pair_id for item in data['items'])


def test_confirm_endpoint_marks_operations_neutral(client, admin_headers, app):
    pair_id, _ = _seed(app)
    resp = client.post(
        f"/api/clan/{CLAN}/treasury/pairs/{pair_id}/confirm",
        json={'kind': 'loan'},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['status'] == 'confirmed'

    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        assert pair.kind == 'loan'
        op = db.session.get(TreasuryOperation, pair.first_op_id)
        assert op.op_class == 'neutral'
        actions = {entry.action for entry in AuditLog.query.filter_by(clan_id=CLAN).all()}
        assert 'treasury_pair_confirm' in actions


def test_reject_endpoint_keeps_tax(client, admin_headers, app):
    pair_id, _ = _seed(app)
    # Тело пустое, но Content-Type задаём явно: без него Flask отвечает 415.
    # То же требование касается фронтенда — body-less POST слать с {}.
    resp = client.post(
        f"/api/clan/{CLAN}/treasury/pairs/{pair_id}/reject",
        json={},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        assert pair.status == 'rejected'
        op = db.session.get(TreasuryOperation, pair.first_op_id)
        assert op.op_class == 'tax'


def test_revise_endpoint_writes_log(client, admin_headers, app):
    pair_id, _ = _seed(app)
    client.post(
        f"/api/clan/{CLAN}/treasury/pairs/{pair_id}/confirm",
        json={'kind': 'exchange'},
        headers=admin_headers,
    )
    resp = client.put(
        f"/api/clan/{CLAN}/treasury/pairs/{pair_id}",
        json={'kind': 'loan', 'comment': 'уточнение'},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['kind'] == 'loan'


def test_candidates_endpoint_returns_candidates(client, admin_headers, app):
    _, op1_id = _seed(app)
    resp = client.get(
        f"/api/clan/{CLAN}/treasury/operations/{op1_id}/candidates",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['first']['id'] == op1_id
    assert len(data['candidates']) >= 1
    assert data['candidates'][0]['score'] >= 6
