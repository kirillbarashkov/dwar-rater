"""Regression tests for star-level parsing (legendary items).

Bug: dwar.ru markup changed — the active-star color now lives on a wrapper
SPAN around the star's description block, while star stat values use
color:red/green SPANs inline. The old regex grabbed the first color after
each <U>N★</U> marker (a stat color) and reported the wrong star level
(Поножи Агония: real 2★, parsed 5★).
"""

from shared.services.processor import _parse_star_level


# Real-shape markup (from -Витчер-, Поножи Агония, 2★ legendary):
# - star 1 block: plain STRONG (no green wrapper) — inactive in this variant
# - star 2 block: wrapped in <SPAN style="color:green"> — ACTIVE star
# - stars 3-5: plain STRONG — not reached yet
AGONIYA_DESC = (
    'Редкое по качеству снаряжение. <br /><br />'
    '<STRONG><U>1★</U></STRONG>'
    '<STRONG>2% увеличение урона. Шанс 11% снизить сопротивления противника '
    'на <SPAN style="color:red">3%</SPAN> на <SPAN style="color:red">5</SPAN> ходов.</STRONG>'
    '<br /><br />'
    '<SPAN style="color:green">'
    '<STRONG><U>2★</U></STRONG>'
    '<STRONG><SPAN style="color:green">2% увеличение урона.</SPAN> Шанс 12% снизить '
    'сопротивления противника на <SPAN style="color:red">6%</SPAN>.</STRONG>'
    '</SPAN>'
    '<br /><br />'
    '<STRONG><U>3★</U></STRONG>'
    '<STRONG>3% увеличение урона. Шанс 12% на <SPAN style="color:red">6%</SPAN> ходов.</STRONG>'
    '<br /><br />'
    '<STRONG><U>4★</U></STRONG>'
    '<STRONG>3% увеличение урона. Шанс 13% на <SPAN style="color:red">7%</SPAN> ходов.</STRONG>'
    '<br /><br />'
    '<STRONG><U>5★</U></STRONG>'
    '<STRONG>4% увеличение урона. Шанс 13% на <SPAN style="color:red">7%</SPAN> ходов.</STRONG>'
)


def test_legendary_active_star_wrapped_in_green():
    """Агония: green wrapper marks star 2 as the current one → 2, not 5."""
    assert _parse_star_level(AGONIYA_DESC) == 2


def test_all_stars_gray_means_zero():
    gray_desc = (
        '<STRONG><U>1★</U></STRONG><STRONG>текст <SPAN style="color:808080">x</SPAN></STRONG>'
        '<STRONG><U>2★</U></STRONG><STRONG>текст <SPAN style="color:808080">y</SPAN></STRONG>'
    )
    assert _parse_star_level(gray_desc) == 0


def test_star_red_wrapper_current():
    """Old-style exotic markup: red color directly marks the active star."""
    red_desc = (
        '<STRONG><U>1★</U></STRONG><STRONG>текст</STRONG>'
        '<STRONG><U>2★</U></STRONG><STRONG>текст <SPAN style="color:red">2</SPAN></STRONG>'
        '<STRONG><U>3★</U></STRONG><STRONG>текст <SPAN style="color:808080">3</SPAN></STRONG>'
    )
    # Old behavior: last active-colored (red) star = 2
    assert _parse_star_level(red_desc) == 2


def test_star_inline_green_stat_not_confused_when_no_wrapper():
    """Inline green stat color must not be read as an active star when the
    real active star is marked by a wrapper elsewhere."""
    desc = (
        '<STRONG><U>1★</U></STRONG><STRONG>текст <SPAN style="color:green">1%</SPAN></STRONG>'
        '<br />'
        '<SPAN style="color:green"><STRONG><U>2★</U></STRONG><STRONG>текст</STRONG></SPAN>'
        '<STRONG><U>3★</U></STRONG><STRONG>текст <SPAN style="color:red">7</SPAN></STRONG>'
    )
    assert _parse_star_level(desc) == 2
