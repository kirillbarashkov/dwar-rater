"""API tests for the chat-ready markdown summaries.

The summary must agree with the «Сальдо» tab it is taken from: totals and the
debtor list come from the same ledger chain, so a pasted summary cannot
contradict the screen. That consistency is what these tests pin down.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    TaxCarryover,
    TreasuryOperation,
)

CLAN = 987208


def _seed(app, members=(), operations=(), carryovers=()):
    with app.app_context():
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        TaxCarryover.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='SummaryClan'))
        for nick, level in members:
            db.session.add(
                ClanMemberInfo(clan_id=CLAN, nick=nick, level=level, join_date='01.01.2026')
            )
        for day, month, year, nick, quantity in operations:
            db.session.add(
                TreasuryOperation(
                    clan_id=CLAN,
                    date=f'{day:02d}.{month:02d}.{year} 12:00',
                    nick=nick,
                    operation_type='Деньги',
                    object_name='Монеты',
                    quantity=quantity,
                )
            )
        for nick, month, year, amount, status in carryovers:
            db.session.add(
                TaxCarryover(
                    clan_id=CLAN,
                    nick=nick,
                    source_month=month,
                    source_year=year,
                    amount=amount,
                    status=status,
                )
            )
        db.session.commit()


def _today():
    today = date.today()
    return today.year, today.month


def _summary(client, headers, kind, **params):
    query = {'kind': kind, **params}
    return client.get(f'/api/clan/{CLAN}/treasury/summary', query_string=query, headers=headers)


def _ledger_debt(client, headers, year, month):
    body = client.get(
        f'/api/clan/{CLAN}/tax-ledger',
        query_string={
            'from_month': month,
            'from_year': year,
            'to_month': month,
            'to_year': year,
        },
        headers=headers,
    ).get_json()
    return body['totals']['debt']


def test_summary_requires_auth(app, client):
    _seed(app, members=[('Alpha', 19)])
    assert _summary(client, None, 'totals').status_code == 401


def test_summary_is_readable_by_a_plain_user(app, client, user_headers):
    _seed(app, members=[('Alpha', 19)])
    assert _summary(client, user_headers, 'totals').status_code == 200


def test_an_unknown_kind_is_refused_with_the_list_of_kinds(app, client, user_headers):
    _seed(app, members=[('Alpha', 19)])
    resp = _summary(client, user_headers, 'everything')
    assert resp.status_code == 400
    assert resp.get_json()['kinds'] == ['carryovers', 'debtors', 'totals']


def test_a_bad_period_is_refused(app, client, user_headers):
    _seed(app, members=[('Alpha', 19)])
    assert _summary(client, user_headers, 'totals', month=13, year=2026).status_code == 400
    assert _summary(client, user_headers, 'totals', month=1, year=1999).status_code == 400


def test_totals_are_three_numbers_and_the_debtor_count(app, client, user_headers):
    year, month = _today()
    _seed(
        app,
        members=[('Alpha', 19), ('Beta', 19)],
        operations=[(5, month, year, 'Alpha', 60)],
    )
    body = _summary(client, user_headers, 'totals', month=month, year=year).get_json()
    text = body['markdown']

    assert body['kind'] == 'totals'
    assert f'**Налоги за {"октябрь" if month == 10 else "—"} {year}**' in text or '**Налоги за' in text
    assert 'Собрано: **60**' in text
    assert 'Ожидалось: 200' in text
    assert 'Не собрано: **140**' in text
    assert 'Должников: 2 из 2' in text


def test_the_missing_amount_equals_the_ledger_debt(app, client, user_headers):
    year, month = _today()
    _seed(
        app,
        members=[('Alpha', 19), ('Beta', 19)],
        operations=[(5, month, year, 'Alpha', 60)],
    )
    text = _summary(client, user_headers, 'totals', month=month, year=year).get_json()['markdown']
    missing = int(text.split('Не собрано: **')[1].split('**')[0])
    assert missing == _ledger_debt(client, user_headers, year, month) == 140


def test_debtors_are_a_flat_list_that_matches_the_totals(app, client, user_headers):
    year, month = _today()
    _seed(
        app,
        members=[('Alpha', 19), ('Beta', 19), ('Gamma', 1)],
        operations=[(5, month, year, 'Alpha', 60)],
    )
    body = _summary(client, user_headers, 'debtors', month=month, year=year).get_json()
    text = body['markdown']

    assert '**Должники за' in text and '(3)' in text
    assert '- **Alpha** — 40 (заплатил 60)' in text
    assert '- **Beta** — 100' in text
    assert '- **Gamma** — 10' in text
    assert 'Итого долг: **150**' in text
    # A clan chat shows pipes and dashes as a wall of characters, not a table.
    assert '|' not in text and '---' not in text

    totals = _summary(client, user_headers, 'totals', month=month, year=year).get_json()['markdown']
    assert 'Не собрано: **150**' in totals


def test_carryovers_are_a_flat_list_with_statuses(app, client, user_headers):
    year, month = _today()
    _seed(
        app,
        members=[('Alpha', 19)],
        carryovers=[
            ('Alpha', month, year, 100, 'confirmed'),
            ('Beta', month, year, 50, 'pending'),
        ],
    )
    body = _summary(client, user_headers, 'carryovers', month=month, year=year).get_json()
    text = body['markdown']

    assert body['count'] == 2
    assert '- **Alpha** — 100 за' in text and '(подтверждён)' in text
    assert '- **Beta** — 50 за' in text and '(ждёт решения)' in text
    assert 'Итого: **150**' in text


def test_a_clan_without_operations_still_answers_honestly(app, client, user_headers):
    year, month = _today()
    _seed(app, members=[('Alpha', 19)])
    body = _summary(client, user_headers, 'totals', month=month, year=year).get_json()

    assert body['reason'] == 'no_operations'
    assert 'Собрано: **0**' in body['markdown']
    assert 'Не собрано: **0**' in body['markdown']

    debtors = _summary(client, user_headers, 'debtors', month=month, year=year).get_json()
    assert 'Долгов нет' in debtors['markdown']
