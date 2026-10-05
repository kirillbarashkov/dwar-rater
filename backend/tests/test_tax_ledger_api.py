"""API tests for the member ledger (/api/clan/<id>/tax-ledger).

Months are pinned to 2020 so the suite never depends on the wall clock (the one
exception asserts the *defaults* against today, not the numbers).

The cleanup in conftest is a silent no-op (TRUNCATE lists a table that does not
exist and the error is swallowed), so every test cleans its own clan's rows and
uses a dedicated clan id — the suite shares one database.
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

CLAN = 987202


def _seed(app, members=(), operations=(), carryovers=()):
    with app.app_context():
        TaxCarryover.query.filter_by(clan_id=CLAN).delete()
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        ClanMemberInfo.query.filter_by(clan_id=CLAN).delete()
        ClanInfo.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()

        db.session.add(ClanInfo(clan_id=CLAN, name='LedgerClan'))
        for nick, level, is_deleted in members:
            db.session.add(
                ClanMemberInfo(
                    clan_id=CLAN, nick=nick, level=level, is_deleted=is_deleted
                )
            )
        for day, month, year, nick, quantity, flagged in operations:
            db.session.add(
                TreasuryOperation(
                    clan_id=CLAN,
                    date=f'{day:02d}.{month:02d}.{year} 12:00',
                    nick=nick,
                    operation_type='Деньги',
                    object_name='Монеты',
                    quantity=quantity,
                    compensation_flag=flagged,
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


def _ledger(client, headers, from_month=1, from_year=2020, to_month=1, to_year=2020):
    url = (
        f'/api/clan/{CLAN}/tax-ledger'
        f'?from_month={from_month}&from_year={from_year}'
        f'&to_month={to_month}&to_year={to_year}'
    )
    return client.get(url, headers=headers)


def _row(body, nick):
    for row in body['rows']:
        if row['nick'] == nick:
            return row
    raise AssertionError(f'{nick} missing from {[r["nick"] for r in body["rows"]]}')


def test_ledger_requires_auth(app, client):
    _seed(app, members=[('Alpha', 5, False)])
    resp = _ledger(client, None)
    assert resp.status_code == 401


def test_ledger_is_readable_by_a_plain_user(app, client, user_headers):
    """The tax tab is open to any member, so its ledger view is too."""
    _seed(app, members=[('Alpha', 5, False)], operations=[(10, 1, 2020, 'Alpha', 10, False)])
    resp = _ledger(client, user_headers)
    assert resp.status_code == 200


def test_ledger_reports_rows_and_totals(app, client, user_headers):
    _seed(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 310, False)],
    )
    body = _ledger(client, user_headers, 1, 2020, 3, 2020).get_json()

    row = _row(body, 'Alpha')
    assert row['paid_total'] == 310
    assert row['norm_total'] == 30  # three months x 10
    assert row['carried_out_final'] == 280
    assert row['debt'] == 0
    assert row['balance'] == 280
    assert [m['month'] for m in row['months']] == [1, 2, 3]

    assert body['totals']['paid_total'] == 310
    assert body['totals']['balance'] == 280
    assert body['from_month'] == 1 and body['to_year'] == 2020


def test_ledger_rejects_a_bad_month(app, client, user_headers):
    _seed(app, members=[('Alpha', 5, False)])
    assert _ledger(client, user_headers, 0, 2020, 1, 2020).status_code == 400
    assert _ledger(client, user_headers, 1, 2020, 13, 2020).status_code == 400


def test_ledger_rejects_a_reversed_period(app, client, user_headers):
    _seed(app, members=[('Alpha', 5, False)])
    assert _ledger(client, user_headers, 3, 2020, 1, 2020).status_code == 400


def test_cancelled_carryover_does_not_credit_the_next_month(app, client, user_headers):
    """A month the treasurer rejected must not reappear as a credit."""
    _seed(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 310, False)],
        carryovers=[('Alpha', 1, 2020, 300, 'cancelled')],
    )
    body = _ledger(client, user_headers, 2, 2020, 2, 2020).get_json()
    row = _row(body, 'Alpha')
    assert row['carried_in_total'] == 0
    assert row['debt'] == 10
    assert row['balance'] == -10


def test_confirmed_carryover_credits_the_next_month(app, client, user_headers):
    _seed(
        app,
        members=[('Alpha', 5, False)],
        operations=[(10, 1, 2020, 'Alpha', 310, False)],
        carryovers=[('Alpha', 1, 2020, 300, 'confirmed')],
    )
    body = _ledger(client, user_headers, 2, 2020, 2, 2020).get_json()
    row = _row(body, 'Alpha')
    assert row['carried_in_total'] == 300
    assert row['debt'] == 0
    assert row['carried_out_final'] == 290
    assert row['balance'] == 290


def test_departed_member_is_not_in_the_ledger(app, client, user_headers):
    _seed(
        app,
        members=[('Gone', 5, True)],
        operations=[(10, 1, 2020, 'Gone', 250, False)],
    )
    body = _ledger(client, user_headers).get_json()
    assert body['rows'] == []
    assert body['reason'] == 'no_operations'


def test_ledger_defaults_to_the_current_year(app, client, user_headers):
    _seed(app, members=[('Alpha', 5, False)], operations=[(10, 1, 2020, 'Alpha', 10, False)])
    resp = client.get(f'/api/clan/{CLAN}/tax-ledger', headers=user_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    today = date.today()
    assert body['from_year'] == today.year and body['from_month'] == 1
    assert body['to_year'] == today.year and body['to_month'] == today.month
