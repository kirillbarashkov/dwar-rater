"""Аномалии казны (detect_anomalies) — pure service tests.

The detector is a diagnostic: it must find real problems without inventing false
ones (a clan legitimately has members who left and people who prepay), and it
must mark the two actual corruptions as blocking.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.services.treasury_anomalies import detect_anomalies

TODAY = date(2026, 10, 5)


def op(op_id, day, month, year, nick, quantity, flagged=False):
    return {
        "id": op_id,
        "date": f"{day:02d}.{month:02d}.{year} 12:00",
        "nick": nick,
        "operation_type": "Деньги",
        "object_name": "Монеты",
        "quantity": quantity,
        "compensation_flag": flagged,
    }


def member(nick, level=5, join_date="", is_deleted=False):
    return {"nick": nick, "level": level, "join_date": join_date, "is_deleted": is_deleted}


def codes(result):
    return {item["code"]: item for item in result["items"]}


def test_a_clean_treasury_reports_nothing():
    result = detect_anomalies(
        [op(1, 5, 10, 2026, "Alpha", 10)],
        [member("Alpha")],
        today=TODAY,
    )
    assert result["items"] == []
    assert result["total"] == 0
    assert result["checked"] == {"operations": 1, "members": 1}


def test_future_date_is_blocking():
    result = detect_anomalies(
        [op(1, 5, 12, 2026, "Alpha", 10)],
        [member("Alpha")],
        today=TODAY,
    )
    item = codes(result)["future_date"]
    assert item["count"] == 1
    assert item["blocking"] is True
    assert item["examples"][0]["id"] == 1


def test_negative_quantity_is_blocking():
    result = detect_anomalies(
        [op(7, 5, 10, 2026, "Alpha", -50)],
        [member("Alpha")],
        today=TODAY,
    )
    item = codes(result)["negative_quantity"]
    assert item["count"] == 1
    assert item["blocking"] is True


def test_payment_before_joining_is_flagged_with_the_start_month():
    result = detect_anomalies(
        [op(1, 10, 1, 2020, "Alpha", 10)],
        [member("Alpha", join_date="10.06.2020")],
        today=TODAY,
    )
    item = codes(result)["before_join"]
    assert item["count"] == 1
    assert item["blocking"] is False
    assert "07.2020" in item["examples"][0]["note"]


def test_payment_from_a_nick_outside_the_roster_is_flagged_but_not_blocked():
    result = detect_anomalies(
        [op(1, 5, 10, 2026, "Ghost", 10)],
        [member("Alpha")],
        today=TODAY,
    )
    item = codes(result)["unknown_nick"]
    assert item["count"] == 1
    assert item["blocking"] is False


def test_a_big_payment_is_measured_against_the_norm():
    # Level 5 -> norm 10, so the threshold is 30.
    flagged = detect_anomalies(
        [op(1, 5, 10, 2026, "Alpha", 30)],
        [member("Alpha", level=5)],
        today=TODAY,
    )
    item = codes(flagged)["above_norm"]
    assert item["count"] == 1
    assert "норма 10" in item["examples"][0]["note"]

    normal = detect_anomalies(
        [op(2, 5, 10, 2026, "Alpha", 29)],
        [member("Alpha", level=5)],
        today=TODAY,
    )
    assert normal["items"] == []


def test_compensation_rows_are_not_rated_against_the_norm():
    """A «зачёт» is a waiver, not a payment — the norm rule does not apply."""
    result = detect_anomalies(
        [op(1, 5, 10, 2026, "Alpha", 500, flagged=True)],
        [member("Alpha", level=5)],
        today=TODAY,
    )
    assert "above_norm" not in codes(result)


def test_counts_are_exact_and_examples_are_capped():
    operations = [op(i, 5, 10, 2026, f"Ghost{i}", 10) for i in range(1, 9)]
    result = detect_anomalies(operations, [member("Alpha")], today=TODAY)
    item = codes(result)["unknown_nick"]
    assert item["count"] == 8          # the count is the truth
    assert len(item["examples"]) == 5  # the payload stays small
    assert result["total"] == 8


def test_items_are_sorted_by_count_descending():
    operations = [
        op(1, 5, 12, 2026, "Alpha", 10),   # future date (December)
        op(2, 5, 9, 2026, "Ghost", 10),    # past date, unknown nick
        op(3, 5, 10, 2026, "Ghost2", 10),  # unknown nick as well
    ]
    result = detect_anomalies(operations, [member("Alpha")], today=TODAY)
    assert [item["code"] for item in result["items"]] == ["unknown_nick", "future_date"]
