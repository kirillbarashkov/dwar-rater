"""Regression: the treasury parser must accept every row flavour dwar.ru uses.

dwar renders 20 operations per report page and alternates the row markup:
``<tr class="bg_l">`` / ``<tr class="">`` (older pages used a bare ``<tr>``).
The parser used to match only the first two flavours, so every second
operation — tax payments included — was dropped with no warning at all,
because the row regex never even saw those rows.

Real-world shape of one operation row:
  <tr class=""> <td class="brd-all p6h">date</td>
                <td class="brd-all p6h">userToTag('nick')</td>
                <td class="brd-all p6h">Деньги|Склад|…</td>
                <td class="brd-all p6h"><a>object</a></td>
                <td class="brd-all p6h"><span style="color: green">100</span></td>
  </tr>
"""
from shared.services.clan_parser import parse_clan_treasury_operations

CELL = 'class="brd-all p6h"'

# One row per flavour, plus a withdrawal (red) so the sign is covered.
HTML = f"""
<html><body><table>
<tr height="22"><td><img src="images/tbl-x.gif"></td></tr>
<tr class="bg_l"><td {CELL}>09.09.2026 20:05</td>
  <td {CELL}>userToTag('_ Sanych_')</td>
  <td {CELL}>Склад</td>
  <td {CELL}><a>Трофей «Когти редкого зверя»</a></td>
  <td {CELL}><span style="color: green">11</span></td></tr>
<tr class=""><td {CELL}>09.09.2026 20:03</td>
  <td {CELL}>userToTag('_ Sanych_')</td>
  <td {CELL}>Деньги</td>
  <td {CELL}><a>Монеты</a></td>
  <td {CELL}><span style="color: green">100</span></td></tr>
<tr><td {CELL}>09.09.2026 20:02</td>
  <td {CELL}>userToTag('A e r i s')</td>
  <td {CELL}>Склад</td>
  <td {CELL}><a>Сущность Корра</a></td>
  <td {CELL}><span style="color: green">400</span></td></tr>
<tr class=""><td {CELL}>09.09.2026 20:01</td>
  <td {CELL}>userToTag('SoullR')</td>
  <td {CELL}>Деньги</td>
  <td {CELL}><a>Монеты</a></td>
  <td {CELL}><span style="color: red">-928</span></td></tr>
</table></body></html>
"""


def test_all_row_flavours_are_parsed():
    ops = parse_clan_treasury_operations(HTML)
    assert len(ops) == 4, ops


def test_empty_class_row_money_payment_is_parsed():
    """The exact shape that used to disappear from the report."""
    ops = parse_clan_treasury_operations(HTML)
    money = [o for o in ops if o["operation_type"] == "Деньги" and o["quantity"] == 100]
    assert money, ops
    assert money[0]["nick"] == "_ Sanych_"
    assert money[0]["date"] == "09.09.2026 20:03"
    assert money[0]["object_name"] == "Монеты"


def test_plain_and_bg_l_rows_still_parsed():
    ops = parse_clan_treasury_operations(HTML)
    thirds = {(o["nick"], o["object_name"]): o for o in ops}
    assert ("_ Sanych_", "Трофей «Когти редкого зверя»") in thirds  # bg_l
    assert ("A e r i s", "Сущность Корра") in thirds  # bare <tr>


def test_withdrawal_keeps_negative_sign():
    ops = parse_clan_treasury_operations(HTML)
    s = [o for o in ops if o["nick"] == "SoullR"]
    assert s and s[0]["quantity"] == -928, s


def test_chrome_rows_are_not_turned_into_operations():
    ops = parse_clan_treasury_operations(HTML)
    for op in ops:
        assert op["operation_type"] in ("Деньги", "Склад"), op
