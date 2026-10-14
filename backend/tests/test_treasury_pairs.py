"""Поиск пар казны: чистые функции, база не нужна."""

from shared.services.treasury_pairs import candidate_score, dry_run, find_candidates


def money_op(**kw):
    base = {
        'id': 1,
        'date': '01.10.2026',
        'nick': 'Hero',
        'operation_type': 'Деньги',
        'object_name': 'Монеты',
        'quantity': 100,
    }
    base.update(kw)
    return base


def item_op(**kw):
    base = {
        'id': 2,
        'date': '01.10.2026',
        'nick': 'Hero',
        'operation_type': 'Предмет',
        'object_name': 'Сущность Гальфиды',
        'quantity': -5,
    }
    base.update(kw)
    return base


def test_money_against_resource_same_day_is_the_strongest_signal():
    # 3 (та же дата) + 2 (противоположные знаки) + 1 (разные объекты) + 2 (деньги/ресурс)
    assert candidate_score(money_op(), item_op()) == 8


def test_same_object_with_opposite_signs_is_not_an_exchange():
    """Тот же объект с обратным знаком — сторно, а не обмен."""
    assert candidate_score(money_op(), money_op(id=3, quantity=-100)) == 0


def test_same_sign_is_not_a_pair():
    assert candidate_score(money_op(), item_op(quantity=5)) == 0


def test_different_nick_is_not_a_pair():
    assert candidate_score(money_op(), item_op(nick='Other')) == 0


def test_window_limits_the_search():
    assert candidate_score(money_op(), item_op(date='05.10.2026')) == 0
    assert candidate_score(money_op(), item_op(date='02.10.2026')) > 0


def test_zero_quantity_is_not_a_pair():
    assert candidate_score(money_op(), item_op(quantity=0)) == 0


def test_greedy_matching_uses_each_operation_once():
    """Операция участвует максимум в одной паре.

    Без этого правила на реальных данных 15 432 операции давали 32 269 «пар»:
    одна операция становилась кандидатом для десятков других.
    """
    ops = [
        money_op(id=1),
        item_op(id=2),
        item_op(id=3, object_name='Другой ресурс', quantity=-1),
    ]
    pairs = dry_run(ops)
    assert len(pairs) == 1, 'деньги уходят в одну пару, а не в обе'
    assert pairs[0]['money_involved'] is True


def test_threshold_drops_weak_pairs():
    """Разные ресурсы в разные дни — уверенность 4, порог 6 отсекает такой шум."""
    weak = [
        item_op(id=1),
        item_op(id=2, object_name='Другой ресурс', date='02.10.2026', quantity=3),
    ]
    assert dry_run(weak) == []
    assert len(dry_run(weak, min_score=4)) == 1


def test_find_candidates_excludes_the_operation_itself():
    first = money_op(id=1)
    assert all(op.get('id') != 1 for _, op in find_candidates(first, [first]))
