"""Займы из казны: минусовые операции, не закрытые подтверждённой парой.

Отдельный клан: сервис считает по всем операциям клана, и операции соседних тестов
сделали бы суммы непредсказуемыми.
"""

from shared.models import db
from shared.models.clan_info import ClanInfo, TreasuryOperation, TreasuryOperationPair
from shared.services.treasury_loans import collect_loans

CLAN = 987010


def _setup(app):
    """Клан с минусовыми операциями во всех состояниях, которые различает сервис."""
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="LoansClan"))
            db.session.commit()

        for pair in TreasuryOperationPair.query.filter_by(clan_id=CLAN).all():
            db.session.delete(pair)
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        def op(quantity, op_class='tax', object_name='Гульфия', nick='__LoansProbe__'):
            return TreasuryOperation(
                clan_id=CLAN,
                date='01.10.2026',
                nick=nick,
                operation_type='Предмет',
                object_name=object_name,
                quantity=quantity,
                op_class=op_class,
            )

        # Без пары вовсе — открытый заём.
        alone = op(-10)
        # В паре, которую казначей ещё не разобрал.
        waiting = op(-20)
        waiting_mate = op(20, object_name='Монеты')
        # В подтверждённой паре: минус уже нейтральный, за человеком не числится.
        closed = op(-30, op_class='neutral')
        closed_mate = op(30, object_name='Монеты', op_class='neutral')
        # Исключён правилом группы — в займы не попадает.
        excluded = op(-40, op_class='excluded')
        # Плюсовая операция займом быть не может.
        income = op(50, object_name='Монеты')

        db.session.add_all(
            [alone, waiting, waiting_mate, closed, closed_mate, excluded, income]
        )
        db.session.commit()

        db.session.add_all(
            [
                TreasuryOperationPair(
                    clan_id=CLAN,
                    first_op_id=waiting.id,
                    second_op_id=waiting_mate.id,
                    status='candidate',
                ),
                TreasuryOperationPair(
                    clan_id=CLAN,
                    first_op_id=closed.id,
                    second_op_id=closed_mate.id,
                    status='confirmed',
                ),
            ]
        )
        db.session.commit()


def test_only_open_withdrawals_count(app):
    """Открытыми считаются минусовые вне подтверждённой пары; исключённые — нет."""
    _setup(app)
    with app.app_context():
        data = collect_loans(CLAN)

        assert data['totals']['people'] == 1
        assert data['totals']['ops'] == 2
        assert data['totals']['taken'] == 30  # 10 без пары + 20 в паре на разборе
        assert data['totals']['excluded_hidden'] == 1

        person = data['people'][0]
        assert person['nick'] == '__LoansProbe__'
        assert person['count'] == 2
        assert person['taken'] == 30


def test_reasons_explain_why_open(app):
    """Причина открытия видна: без неё казначей не знает, что делать с суммой."""
    _setup(app)
    with app.app_context():
        person = collect_loans(CLAN)['people'][0]

        assert person['reasons'] == {'none': 1, 'candidate': 1}
        assert person['first_date'] == '01.10.2026'
        assert person['last_date'] == '01.10.2026'


def test_nick_returns_that_persons_operations(app):
    """Операции человека отдаются только по запросу — сводка остаётся лёгкой."""
    _setup(app)
    with app.app_context():
        data = collect_loans(CLAN, nick='__LoansProbe__')

        assert len(data['ops']) == 2
        reasons = sorted(item['reason'] for item in data['ops'])
        assert reasons == ['candidate', 'none']
        # Пара указана: по ней казначей переходит в разбор.
        assert any(item['pair_id'] for item in data['ops'])

        assert 'ops' not in collect_loans(CLAN)
        assert collect_loans(CLAN, nick='__Никого__')['ops'] == []


def test_loans_endpoint(client, admin_headers, app):
    _setup(app)

    resp = client.get(f"/api/clan/{CLAN}/treasury/loans", headers=admin_headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['totals']['taken'] == 30

    with_nick = client.get(
        f"/api/clan/{CLAN}/treasury/loans?nick=__LoansProbe__", headers=admin_headers
    )
    assert with_nick.status_code == 200, with_nick.get_data(as_text=True)
    assert len(with_nick.get_json()['ops']) == 2
