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


RECALC_CLAN = 987009  # отдельный клан: пересчёт считает по всем операциям клана


def _seed_recalc(app):
    """Клан с двумя операциями и отклонённой парой — для проверки пересчёта."""
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=RECALC_CLAN).first():
            db.session.add(ClanInfo(clan_id=RECALC_CLAN, name="RecalcClan"))
            db.session.commit()

        for pair in TreasuryOperationPair.query.filter_by(clan_id=RECALC_CLAN).all():
            db.session.delete(pair)
        TreasuryOperation.query.filter_by(clan_id=RECALC_CLAN).delete()
        db.session.commit()

        op1 = TreasuryOperation(
            clan_id=RECALC_CLAN,
            date='01.10.2026',
            nick='__RecalcProbe__',
            operation_type='Деньги',
            object_name='Монеты',
            quantity=100,
        )
        op2 = TreasuryOperation(
            clan_id=RECALC_CLAN,
            date='01.10.2026',
            nick='__RecalcProbe__',
            operation_type='Предмет',
            object_name='Ресурс',
            quantity=-5,
        )
        db.session.add_all([op1, op2])
        db.session.commit()

        pair = TreasuryOperationPair(
            clan_id=RECALC_CLAN,
            first_op_id=op1.id,
            second_op_id=op2.id,
            status='rejected',
        )
        db.session.add(pair)
        db.session.commit()
        return pair.id


def test_recalculate_returns_rejected_pair_to_candidates(client, admin_headers, app):
    """Пересчёт из интерфейса: отклонённая пара снова становится предложением."""
    _seed_recalc(app)

    resp = client.post(
        f"/api/clan/{RECALC_CLAN}/treasury/pairs/recalculate",
        json={},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['rejected_freed'] == 1
    assert data['created'] == 1
    assert data['classes_before'] == data['classes_after']

    queue = client.get(
        f"/api/clan/{RECALC_CLAN}/treasury/pairs?status=candidate",
        headers=admin_headers,
    )
    assert queue.get_json()['total'] == 1


def test_recalculate_is_audited(client, admin_headers, app):
    """Пересчёт пишется в аудит: правка казны должна быть объяснимой."""
    _seed_recalc(app)

    client.post(
        f"/api/clan/{RECALC_CLAN}/treasury/pairs/recalculate",
        json={},
        headers=admin_headers,
    )

    with app.app_context():
        log = (
            AuditLog.query.filter_by(
                action='treasury_pairs_recalculate', clan_id=RECALC_CLAN
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert log is not None


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


def test_queue_filters_by_period(client, admin_headers, app):
    """Период считается по месяцу операций: мимо дат — пусто."""
    _seed(app)

    hit = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate"
        f"&date_from=2026-10&date_to=2026-10",
        headers=admin_headers,
    )
    assert hit.status_code == 200, hit.get_data(as_text=True)
    assert hit.get_json()['total'] >= 1

    miss = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate&date_from=2027-01",
        headers=admin_headers,
    )
    assert miss.get_json()['total'] == 0


def test_queue_filters_by_operation_type(client, admin_headers, app):
    """Тип операции ищется на любой стороне пары."""
    _seed(app)

    money = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate&op_type=Деньги",
        headers=admin_headers,
    )
    assert money.get_json()['total'] >= 1

    nothing = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate&op_type=Такого нет",
        headers=admin_headers,
    )
    assert nothing.get_json()['total'] == 0


def test_queue_pagination_limits_page(client, admin_headers, app):
    """Страница отдаёт не больше запрошенного, а total — общее число."""
    _seed(app)

    resp = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate&limit=1&offset=0",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert len(data['items']) == 1
    assert data['total'] >= 1


def test_queue_focuses_single_pair_ignoring_status(client, admin_headers, app):
    """Переход из «Статуса персонажа»: пара видна независимо от статуса.

    Подтверждённая пара не попадает в очередь кандидатов, поэтому фокус по pair_id
    отбор по статусу игнорирует — иначе переход вёл бы в пустой экран.
    """
    pair_id, _ = _seed(app)
    client.post(
        f"/api/clan/{CLAN}/treasury/pairs/{pair_id}/confirm",
        json={'kind': 'exchange'},
        headers=admin_headers,
    )

    without_focus = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate", headers=admin_headers
    )
    assert all(item['id'] != pair_id for item in without_focus.get_json()['items'])

    focused = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate&pair_id={pair_id}",
        headers=admin_headers,
    )
    assert focused.status_code == 200, focused.get_data(as_text=True)
    data = focused.get_json()
    assert data['total'] == 1
    assert data['items'][0]['id'] == pair_id
    assert data['items'][0]['status'] == 'confirmed'


def test_queue_hides_candidates_with_excluded_objects(client, admin_headers, app):
    """Кандидат с исключённым объектом не предлагается: казначею нечего решать.

    Пара не удаляется — она просто перестаёт предлагаться, пока действует правило.
    """
    pair_id, _ = _seed(app)

    created = client.post(
        f"/api/clan/{CLAN}/treasury/exclusions",
        json={'name': 'Ресурсы', 'mode': 'exclude', 'prefixes': ['Ресурс']},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.get_data(as_text=True)

    resp = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?status=candidate", headers=admin_headers
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert all(item['id'] != pair_id for item in data['items'])
    assert data['hidden_excluded'] >= 1

    # В режиме фокуса пара остаётся видимой: переход из «Статуса персонажа» не должен
    # упираться в пустой экран.
    focused = client.get(
        f"/api/clan/{CLAN}/treasury/pairs?pair_id={pair_id}", headers=admin_headers
    )
    assert focused.status_code == 200, focused.get_data(as_text=True)
    assert focused.get_json()['total'] == 1
