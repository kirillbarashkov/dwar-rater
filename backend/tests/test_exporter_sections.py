"""A28: `shared/services/exporter.py` (758 строк) не был покрыт ни одним тестом.

Экспорт — единственное место, где данные, пришедшие со **скрейпленной** страницы,
превращаются в HTML, который открывает браузер. Поэтому здесь два вида проверок:

* каждый раздел рендерится в обоих форматах хотя бы на минимальных данных
  (раньше любой из девяти разделов мог упасть с `KeyError`, и узнали бы мы об
  этом от пользователя);
* HTML **экранирует** содержимое: имя и ранг персонажа приходят из внешнего
  источника, и `<script>` в них не должен становиться тегом.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from shared.services.exporter import export_to_html, export_to_markdown

SECTIONS = [
    'identity', 'combat_stats', 'characteristics', 'equipment',
    'effects', 'medals', 'records', 'professions', 'additional',
]

MINIMAL = {'name': 'Гимли', 'race': 'Гном', 'rank': 'Воин', 'level': 20, 'clan': 'Тест'}


@pytest.mark.parametrize('section', SECTIONS)
def test_every_section_renders_in_both_formats(section):
    html = export_to_html(MINIMAL, [section])
    markdown = export_to_markdown(MINIMAL, [section])

    assert html and len(html) > 100, f'раздел {section}: html пустой'
    assert markdown and markdown.strip(), f'раздел {section}: markdown пустой'


def test_all_sections_together_render():
    html = export_to_html(MINIMAL, SECTIONS)
    markdown = export_to_markdown(MINIMAL, SECTIONS)

    assert html.count('<div') > len(SECTIONS) // 2
    assert 'Гимли' in markdown


def test_unknown_section_is_ignored_not_fatal():
    """Лишний раздел не должен ронять экспорт целиком."""
    html = export_to_html(MINIMAL, ['identity', 'galactic'])
    assert 'Гимли' in html


def test_html_escapes_character_name_from_scraped_page():
    """Имя приходит со страницы игры — тег в нём не должен стать тегом."""
    data = dict(MINIMAL, name='<script>alert(1)</script>', rank='<b>Воин</b>')
    html = export_to_html(data, ['identity'])

    assert '<script>alert(1)</script>' not in html, 'HTML не экранирует имя персонажа'
    assert '&lt;script&gt;' in html or '&amp;lt;script' in html


def test_markdown_survives_cyrillic():
    markdown = export_to_markdown(dict(MINIMAL, clan='Гномы и Ко'), ['identity'])
    assert 'Гномы и Ко' in markdown


def test_empty_name_falls_back_instead_of_crashing():
    html = export_to_html({'name': ''}, ['identity'])
    assert html


def test_page_format_changes_html():
    landscape = export_to_html(MINIMAL, ['identity'], 'landscape')
    portrait = export_to_html(MINIMAL, ['identity'], 'portrait')

    assert landscape != portrait, 'ориентация страницы ни на что не влияет'
    assert 'landscape' in landscape and 'portrait' in portrait
