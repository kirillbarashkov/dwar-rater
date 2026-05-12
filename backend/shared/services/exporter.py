"""Character analysis exporter — generates HTML, Markdown, and PDF reports.

Exports match the UI exactly: same data, same grouping, same order.
PDF uses WeasyPrint with @page rules for landscape/portrait orientation.
"""

import re
from datetime import datetime, timezone


SECTION_LABELS = {
    'identity': 'Идентификация',
    'combat_stats': 'Боевая статистика',
    'characteristics': 'Характеристики',
    'equipment': 'Экипировка',
    'effects': 'Эффекты',
    'medals': 'Медали',
    'records': 'Рекорды',
    'professions': 'Профессии',
    'additional': 'Дополнительно',
}

UI_CATEGORIES = {
    'combat': {'label': 'Боевая экипировка', 'icon': '🛡️', 'kinds': {'Шлем', 'Наручи', 'Наплечники', 'Двуручное', 'Основное', 'Левая рука', 'Легкий щит', 'Кираса', 'Поножи', 'Кольчуга', 'Обувь', 'Лук'}},
    'style': {'label': 'Вещи стиля', 'icon': '🎭', 'kinds': {'Шлем', 'Наручи', 'Наплечники', 'Двуручное', 'Основное', 'Левая рука', 'Легкий щит', 'Кираса', 'Поножи', 'Кольчуга', 'Обувь', 'Лук', 'Эффекты', 'Кольца', 'Амулет'}},
    'jewelry': {'label': 'Ювелирка', 'icon': '💍', 'kinds': {'Кольца', 'Амулет'}},
    'arkats': {'label': 'Аркаты', 'icon': '💠', 'kinds': {'Браслет', 'Аркат'}},
    'misc': {'label': 'Разное', 'icon': '📦', 'kinds': {'Рюкзак', 'Пояс', 'Ремесленная сумка'}},
}

KIND_TO_CATEGORY = {}
for cat_key, cat_data in UI_CATEGORIES.items():
    for kind in cat_data['kinds']:
        KIND_TO_CATEGORY[kind] = cat_key


def _strip_html(text):
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()


def _esc(text):
    if not text:
        return ''
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))


def _quality_name(quality):
    if isinstance(quality, dict):
        return quality.get('name', '')
    return str(quality)


def _quality_color(quality):
    if isinstance(quality, dict):
        return quality.get('color', '#e0e0e0')
    return '#e0e0e0'


def _group_equipment_by_ui_category(eq_by_kind):
    result = {}
    for cat_key in UI_CATEGORIES:
        result[cat_key] = {}
    for kind, items in eq_by_kind.items():
        if isinstance(items, dict):
            for sub_kind, sub_items in items.items():
                cat = KIND_TO_CATEGORY.get(sub_kind, 'misc')
                result.setdefault(cat, {})[f'{kind} ({sub_kind})'] = sub_items
        else:
            cat = KIND_TO_CATEGORY.get(kind, 'misc')
            result.setdefault(cat, {})[kind] = items
    return {k: v for k, v in result.items() if v}


def _format_item_enchants(enchants):
    if not enchants:
        return {}
    groups = {}
    for e in enchants:
        etype = e.get('type', '')
        if etype:
            groups.setdefault(etype, []).append(e.get('value', ''))
    return groups


# ── HTML Export ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
@page {{
    size: {page_size};
    margin: 15mm;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; line-height: 1.4; }}
.report {{ }}
.report-header {{ background: #1a1a2e; color: white; padding: 16px 20px; }}
.report-header h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
.report-header .subtitle {{ opacity: 0.8; font-size: 0.85rem; }}
.section {{ padding: 14px 20px; border-bottom: 1px solid #eee; page-break-inside: avoid; }}
.section:last-child {{ border-bottom: none; }}
.section-title {{ font-size: 0.95rem; font-weight: 700; color: #1a1a2e; margin-bottom: 10px; padding-bottom: 4px; border-bottom: 2px solid #00d4aa; display: inline-block; }}
.info-grid {{ display: table; width: 100%%; }}
.info-row {{ display: table-row; }}
.info-item {{ display: table-cell; padding: 3px 8px; font-size: 0.8rem; }}
.info-label {{ font-size: 0.65rem; text-transform: uppercase; color: #888; }}
.info-value {{ font-weight: 500; }}
table {{ width: 100%%; border-collapse: collapse; margin-top: 4px; font-size: 0.8rem; }}
th, td {{ padding: 4px 8px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; font-weight: 600; color: #555; font-size: 0.7rem; text-transform: uppercase; }}
.quality-badge {{ display: inline-block; padding: 1px 5px; border-radius: 2px; font-size: 0.7rem; font-weight: 600; }}
.item-card {{ background: #f8f9fa; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; border-left: 3px solid #ccc; page-break-inside: avoid; }}
.item-header {{ font-weight: 600; font-size: 0.85rem; margin-bottom: 3px; }}
.item-stars {{ color: #ffc857; font-size: 0.7rem; }}
.item-details {{ font-size: 0.75rem; color: #555; }}
.item-details span {{ margin-right: 10px; }}
.item-group {{ margin-top: 4px; }}
.item-group-header {{ font-size: 0.65rem; text-transform: uppercase; color: #888; margin-bottom: 2px; font-weight: 600; }}
.item-tag {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 0.7rem; border: 1px solid #ddd; background: white; margin: 1px 2px; }}
.effect-card {{ background: #f8f9fa; border-radius: 4px; padding: 6px 10px; margin-bottom: 6px; }}
.effect-title {{ font-weight: 600; font-size: 0.8rem; }}
.effect-time {{ font-size: 0.7rem; color: #888; }}
.effect-skills {{ font-size: 0.75rem; color: #555; margin-top: 2px; }}
.medal-group {{ margin-bottom: 8px; }}
.medal-group h4 {{ font-size: 0.8rem; color: #555; margin-bottom: 4px; }}
.medal-item {{ padding: 2px 0; font-size: 0.8rem; }}
.category-title {{ font-size: 0.85rem; font-weight: 700; color: #333; margin: 12px 0 6px; padding-bottom: 3px; border-bottom: 1px solid #ddd; }}
.sub-category-title {{ font-size: 0.75rem; font-weight: 600; color: #555; margin: 8px 0 4px; }}
.set-section {{ margin-top: 10px; padding-top: 8px; border-top: 1px solid #ddd; }}
.set-name {{ font-weight: 600; font-size: 0.8rem; margin-bottom: 3px; }}
.set-items {{ font-size: 0.75rem; color: #555; }}
.footer {{ padding: 8px 20px; background: #f8f9fa; text-align: center; font-size: 0.7rem; color: #888; }}
</style>
</head>
<body>
<div class="report">
{body}
</div>
</body>
</html>"""


def export_to_html(data, sections, page_format='landscape'):
    body_parts = []
    name = data.get('name', 'Неизвестный')
    race = data.get('race', '')
    rank = data.get('rank', '')
    title = f'{name}' + (f' — {race}' if race else '')

    page_size = 'A4 landscape' if page_format == 'landscape' else 'A4 portrait'

    body_parts.append(f'''<div class="report-header">
<h1>{_esc(name)}</h1>
<div class="subtitle">{_esc(race)} | {_esc(rank)}</div>
</div>''')

    if 'identity' in sections:
        body_parts.append(_html_identity(data))
    if 'combat_stats' in sections:
        body_parts.append(_html_combat_stats(data))
    if 'characteristics' in sections:
        body_parts.append(_html_characteristics(data))
    if 'equipment' in sections:
        body_parts.append(_html_equipment(data))
    if 'effects' in sections:
        body_parts.append(_html_effects(data))
    if 'medals' in sections:
        body_parts.append(_html_medals(data))
    if 'records' in sections:
        body_parts.append(_html_records(data))
    if 'professions' in sections:
        body_parts.append(_html_professions(data))
    if 'additional' in sections:
        body_parts.append(_html_additional(data))

    now = datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')
    body_parts.append(f'<div class="footer">Dwar Rater — {now}</div>')
    return HTML_TEMPLATE.format(title=_esc(title), body='\n'.join(body_parts), page_size=page_size)


def _html_identity(data):
    items = []
    for key, label in [('name', 'Имя'), ('race', 'Раса'), ('rank', 'Ранг'), ('level', 'Уровень'), ('clan', 'Клан'), ('clan_rank', 'Роль в клане')]:
        val = data.get(key, '')
        if val:
            items.append(f'<div class="info-item"><span class="info-label">{label}</span><br><span class="info-value">{_esc(val)}</span></div>')
    return f'''<div class="section">
<div class="section-title">Идентификация</div>
<div class="info-grid"><div class="info-row">{''.join(items)}</div></div>
</div>'''


def _html_combat_stats(data):
    rows = []
    for key, label in [('wins', 'Победы'), ('losses', 'Поражения'), ('winrate', 'Винрейт'), ('kills', 'Убийства')]:
        val = data.get(key, '')
        if val:
            rows.append(f'<tr><td>{label}</td><td>{_esc(str(val))}</td></tr>')
    gb = data.get('great_battles', {})
    if gb:
        for key, label in [('wins', 'Победы в ВБ'), ('total', 'Участий в ВБ'), ('winrate', 'Винрейт ВБ')]:
            val = gb.get(key, '')
            if val:
                rows.append(f'<tr><td>{label}</td><td>{_esc(str(val))}</td></tr>')
    return f'''<div class="section">
<div class="section-title">Боевая статистика</div>
<table><thead><tr><th>Параметр</th><th>Значение</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</div>'''


def _html_characteristics(data):
    groups = [
        ('Основные', data.get('main_stats', {})),
        ('Боевые', data.get('combat_stats', {})),
        ('Магические', data.get('magic_stats', {})),
        ('Социальные', data.get('social', {})),
        ('Достижения', data.get('achievements', {})),
    ]
    parts = []
    for title, stats in groups:
        if not stats:
            continue
        rows = ''.join(f'<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>' for k, v in stats.items())
        parts.append(f'<div style="margin-bottom:8px"><h4 style="font-size:0.8rem;color:#555;margin-bottom:3px">{title}</h4><table><tbody>{rows}</tbody></table></div>')
    return f'''<div class="section">
<div class="section-title">Характеристики</div>
{''.join(parts)}
</div>'''


def _html_equipment(data):
    eq_by_kind = data.get('equipment_by_kind', {})
    sets = data.get('sets', {})
    if not eq_by_kind:
        return ''
    ui_groups = _group_equipment_by_ui_category(eq_by_kind)
    parts = []
    for cat_key in ['combat', 'style', 'jewelry', 'arkats', 'misc']:
        cat_data = UI_CATEGORIES.get(cat_key, {})
        cat_items = ui_groups.get(cat_key, {})
        if not cat_items:
            continue
        parts.append(f'<div class="category-title">{cat_data.get("icon", "")} {cat_data.get("label", cat_key)}</div>')
        for sub_name, items in cat_items.items():
            if not items:
                continue
            if ' (' in sub_name:
                parts.append(f'<div class="sub-category-title">{_esc(sub_name)}</div>')
            parts.extend(_html_equipment_items(items))
    if sets:
        set_parts = []
        for set_name, set_items in sets.items():
            set_parts.append(f'<div class="set-section"><div class="set-name">{_esc(set_name)}</div><div class="set-items">{", ".join(_esc(i) for i in set_items)}</div></div>')
        parts.append(''.join(set_parts))
    return f'''<div class="section">
<div class="section-title">Экипировка</div>
{''.join(parts)}
</div>'''


def _html_equipment_items(items):
    if not items:
        return []
    cards = []
    for item in items:
        qname = _quality_name(item.get('quality', {}))
        qcolor = _quality_color(item.get('quality', {}))
        title = item.get('title', '')
        level = item.get('level', '')
        stars = item.get('star_level', 0)
        star_str = '<span class="item-stars">' + '★' * stars + '☆' * (5 - stars) + '</span>' if stars > 0 else ''
        dur = item.get('durability', '')
        set_name = item.get('set', '')
        details = []
        if level:
            details.append(f'<span>Ур: {_esc(level)}</span>')
        if star_str:
            details.append(f'<span>{star_str}</span>')
        if dur:
            details.append(f'<span>Прочность: {_esc(dur)}</span>')
        if set_name:
            details.append(f'<span>Сет: {_esc(set_name)}</span>')
        # Pattern skills
        pattern_skills = item.get('pattern_skills', [])
        pattern_skills_html = ''
        if pattern_skills:
            skill_tags = ''.join(f'<span class="item-tag" style="color:#339900;border-color:#339900">{_esc(s.get("title", ""))}: {_esc(s.get("value", ""))}</span>' for s in pattern_skills if s.get('title'))
            pattern_skills_html = f'<div class="item-group"><div class="item-group-header">Характеристики узора</div><div class="item-group-content">{skill_tags}</div></div>'
        # Stone skills
        stone_skills = item.get('stone_skills', [])
        stone_skills_html = ''
        if stone_skills:
            skill_tags = ''.join(f'<span class="item-tag" style="color:#f400a1;border-color:#f400a1">{_esc(s.get("title", ""))}: {_esc(s.get("value", ""))}</span>' for s in stone_skills if s.get('title'))
            stone_skills_html = f'<div class="item-group"><div class="item-group-header">Характеристики камня</div><div class="item-group-content">{skill_tags}</div></div>'
        skills = item.get('skills', [])
        skills_html = ''
        if skills:
            skill_tags = ''.join(f'<span class="item-tag" style="color:{_esc(s.get("color", "#333"))};border-color:{_esc(s.get("color", "#ddd"))}">{_esc(s.get("title", ""))}: {_esc(s.get("value", ""))}</span>' for s in skills if s.get('title'))
            skills_html = f'<div class="item-group"><div class="item-group-header">Характеристики</div><div class="item-group-content">{skill_tags}</div></div>'
        pattern = item.get('pattern', '')
        pattern_html = ''
        if pattern:
            pattern_html = f'<div class="item-group"><div class="item-group-header">Узор</div><div class="item-group-content"><span class="item-tag">{_esc(_strip_html(pattern))}</span></div></div>'
        stone = item.get('stone', '')
        stone_html = ''
        if stone:
            stone_html = f'<div class="item-group"><div class="item-group-header">Камень</div><div class="item-group-content"><span class="item-tag">{_esc(_strip_html(stone))}</span></div></div>'
        rune = item.get('rune', '')
        rune_html = ''
        if rune:
            rune_html = f'<div class="item-group"><div class="item-group-header">Руна</div><div class="item-group-content"><span class="item-tag">{_esc(_strip_html(rune))}</span></div></div>'
        rune2 = item.get('rune2', '')
        rune2_html = ''
        if rune2:
            rune2_html = f'<div class="item-group"><div class="item-group-header">Руна 2</div><div class="item-group-content"><span class="item-tag">{_esc(_strip_html(rune2))}</span></div></div>'
        runicSetting = item.get('runicSetting', '')
        runic_html = ''
        if runicSetting:
            runic_html = f'<div class="item-group"><div class="item-group-header">Руническая настройка</div><div class="item-group-content"><span class="item-tag">{_esc(_strip_html(runicSetting))}</span></div></div>'
        enchants = item.get('enchants', [])
        enchant_groups = _format_item_enchants(enchants)
        has_stone = item.get('stone', '')
        enchant_labels = {'Руна': 'Руна', 'Руна 2': 'Руна 2', 'Оправа': 'Оправа', 'Лак': 'Лак', 'Пластина': 'Пластина'}
        if not has_stone:
            enchant_labels['Усиление'] = 'Усиление'
        enchant_labels['Встроено'] = 'Встроено'
        enchant_html = ''
        for etype, label in enchant_labels.items():
            values = enchant_groups.get(etype, [])
            if values:
                tags = ''.join(f'<span class="item-tag">{_esc(_strip_html(v))}</span>' for v in values)
                enchant_html += f'<div class="item-group"><div class="item-group-header">{label}</div><div class="item-group-content">{tags}</div></div>'
        symbols = item.get('symbols', [])
        symbols_html = ''
        if symbols:
            tags = ''.join(f'<span class="item-tag">{_esc(_strip_html(s))}</span>' for s in symbols if s)
            if tags:
                symbols_html = f'<div class="item-group"><div class="item-group-header">Символы</div><div class="item-group-content">{tags}</div></div>'
        cards.append(f'''<div class="item-card" style="border-left-color: {qcolor}">
<div class="item-header">
<span style="color: {qcolor}">{_esc(title)}</span>
<span class="quality-badge" style="background: {qcolor}20; color: {qcolor}">{_esc(qname)}</span>
</div>
<div class="item-details">{''.join(details)}</div>
{skills_html}{pattern_skills_html}{stone_skills_html}{pattern_html}{stone_html}{rune_html}{rune2_html}{runic_html}{enchant_html}{symbols_html}
</div>''')
    return cards


def _html_effects(data):
    parts = []
    perm = data.get('permanent_effects', [])
    temp = data.get('temp_effects', [])
    if perm:
        cards = ''.join(_html_effect_card(e, False) for e in perm)
        parts.append(f'<div style="margin-bottom:8px"><h4 style="font-size:0.8rem;color:#555;margin-bottom:4px">Постоянные эффекты</h4>{cards}</div>')
    if temp:
        by_cat = {}
        for e in temp:
            cat = e.get('category', 'other')
            by_cat.setdefault(cat, []).append(e)
        cat_labels = {'buff': 'Баффы', 'elixir': 'Эликсиры', 'mount': 'Маунты', 'debuff': 'Дебаффы', 'other': 'Прочее'}
        for cat_key in ['buff', 'elixir', 'mount', 'debuff', 'other']:
            cat_effects = by_cat.get(cat_key, [])
            if not cat_effects:
                continue
            cards = ''.join(_html_effect_card(e, True) for e in cat_effects)
            parts.append(f'<div style="margin-bottom:8px"><h4 style="font-size:0.8rem;color:#555;margin-bottom:4px">{cat_labels.get(cat_key, cat_key)}</h4>{cards}</div>')
    if not parts:
        return ''
    return f'''<div class="section">
<div class="section-title">Эффекты</div>
{''.join(parts)}
</div>'''


def _html_effect_card(e, show_time):
    title = e.get('title', '')
    time_left = e.get('time_left', '') if show_time else ''
    skills = e.get('skills', [])
    desc = _strip_html(e.get('desc', ''))
    skills_html = ''
    if skills:
        skill_strs = [f"{s.get('title', '')}: {s.get('value', '')}" for s in skills if s.get('title')]
        if skill_strs:
            skills_html = f'<div class="effect-skills">{", ".join(_esc(s) for s in skill_strs)}</div>'
    time_html = f' <span class="effect-time">({_esc(time_left)})</span>' if time_left else ''
    desc_html = f'<div class="effect-skills">{_esc(desc)}</div>' if desc else ''
    return f'''<div class="effect-card">
<div class="effect-title">{_esc(title)}{time_html}</div>
{skills_html}{desc_html}
</div>'''


def _html_medals(data):
    medals = data.get('medals', [])
    if not medals:
        return ''
    by_rep = {}
    for m in medals:
        rep = m.get('reputation', 'Другие')
        by_rep.setdefault(rep, []).append(m)
    parts = []
    for rep, rep_medals in by_rep.items():
        items = ''.join(f'''<div class="medal-item">
<span class="quality-badge" style="background: {_quality_color(m.get('quality', {}))}20; color: {_quality_color(m.get('quality', {}))}">{_esc(_quality_name(m.get('quality', {})))}</span>
{_esc(m.get('title', ''))} <span style="color:#888;font-size:0.7rem">#{m.get('num', '')}</span>
{_esc(_strip_html(m.get('description', '')))}
</div>''' for m in rep_medals)
        parts.append(f'<div class="medal-group"><h4>{_esc(rep)}</h4>{items}</div>')
    return f'''<div class="section">
<div class="section-title">Медали</div>
{''.join(parts)}
</div>'''


def _html_records(data):
    records = data.get('combat_records', {})
    if not records:
        return ''
    rows = ''.join(f'<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>' for k, v in records.items())
    return f'''<div class="section">
<div class="section-title">Рекорды</div>
<table><thead><tr><th>Рекорд</th><th>Значение</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>'''


def _html_professions(data):
    profs = data.get('professions', {})
    if not profs:
        return ''
    rows = ''.join(f'<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>' for k, v in profs.items())
    return f'''<div class="section">
<div class="section-title">Профессии</div>
<table><thead><tr><th>Профессия</th><th>Уровень</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>'''


def _html_additional(data):
    items = []
    extra = data.get('flashvars_extra', {})
    personal = data.get('personal_info', {})
    for key, label in [('hp', 'HP'), ('mp', 'MP'), ('gender', 'Пол'), ('online', 'Онлайн'), ('mount', 'Маунт'), ('town', 'Город'), ('location', 'Локация')]:
        val = extra.get(key, '')
        if val:
            items.append(f'<div class="info-item"><span class="info-label">{label}</span><br><span class="info-value">{_esc(val)}</span></div>')
    for key, label in [('birthday', 'День рождения'), ('about', 'О персонаже')]:
        val = personal.get(key, '')
        if val:
            items.append(f'<div class="info-item"><span class="info-label">{label}</span><br><span class="info-value">{_esc(_strip_html(val))}</span></div>')
    manor = data.get('manor_location', '')
    if manor:
        items.append(f'<div class="info-item"><span class="info-label">Усадьба</span><br><span class="info-value">{_esc(manor)}</span></div>')
    buildings = data.get('manor_buildings', [])
    if buildings:
        items.append(f'<div class="info-item"><span class="info-label">Здания усадьбы</span><br><span class="info-value">{_esc(", ".join(buildings))}</span></div>')
    if not items:
        return ''
    return f'''<div class="section">
<div class="section-title">Дополнительно</div>
<div class="info-grid"><div class="info-row">{''.join(items)}</div></div>
</div>'''


# ── Markdown Export ──────────────────────────────────────────────────────────

def export_to_markdown(data, sections, page_format='landscape'):
    lines = []
    name = data.get('name', 'Неизвестный')
    race = data.get('race', '')
    rank = data.get('rank', '')
    lines.append(f'# {name}')
    if race or rank:
        lines.append(f'{race} | {rank}')
    lines.append('')
    if 'identity' in sections:
        lines.extend(_md_identity(data))
    if 'combat_stats' in sections:
        lines.extend(_md_combat_stats(data))
    if 'characteristics' in sections:
        lines.extend(_md_characteristics(data))
    if 'equipment' in sections:
        lines.extend(_md_equipment(data))
    if 'effects' in sections:
        lines.extend(_md_effects(data))
    if 'medals' in sections:
        lines.extend(_md_medals(data))
    if 'records' in sections:
        lines.extend(_md_records(data))
    if 'professions' in sections:
        lines.extend(_md_professions(data))
    if 'additional' in sections:
        lines.extend(_md_additional(data))
    now = datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')
    lines.append('')
    lines.append(f'*Dwar Rater — {now}*')
    return '\n'.join(lines)


def _md_identity(data):
    lines = ['## Идентификация', '']
    for key, label in [('name', 'Имя'), ('race', 'Раса'), ('rank', 'Ранг'), ('level', 'Уровень'), ('clan', 'Клан'), ('clan_rank', 'Роль в клане')]:
        val = data.get(key, '')
        if val:
            lines.append(f'- **{label}:** {val}')
    lines.append('')
    return lines


def _md_combat_stats(data):
    lines = ['## Боевая статистика', '', '| Параметр | Значение |', '|----------|----------|']
    for key, label in [('wins', 'Победы'), ('losses', 'Поражения'), ('winrate', 'Винрейт'), ('kills', 'Убийства')]:
        val = data.get(key, '')
        if val:
            lines.append(f'| {label} | {val} |')
    gb = data.get('great_battles', {})
    if gb:
        for key, label in [('wins', 'Победы в ВБ'), ('total', 'Участий в ВБ'), ('winrate', 'Винрейт ВБ')]:
            val = gb.get(key, '')
            if val:
                lines.append(f'| {label} | {val} |')
    lines.append('')
    return lines


def _md_characteristics(data):
    lines = ['## Характеристики', '']
    groups = [('Основные', data.get('main_stats', {})), ('Боевые', data.get('combat_stats', {})), ('Магические', data.get('magic_stats', {})), ('Социальные', data.get('social', {})), ('Достижения', data.get('achievements', {}))]
    for title, stats in groups:
        if not stats:
            continue
        lines.extend([f'### {title}', '', '| Характеристика | Значение |', '|----------------|----------|'])
        for k, v in stats.items():
            lines.append(f'| {k} | {v} |')
        lines.append('')
    return lines


def _md_equipment(data):
    eq_by_kind = data.get('equipment_by_kind', {})
    sets = data.get('sets', {})
    if not eq_by_kind:
        return []
    ui_groups = _group_equipment_by_ui_category(eq_by_kind)
    lines = ['## Экипировка', '']
    for cat_key in ['combat', 'style', 'jewelry', 'arkats', 'misc']:
        cat_data = UI_CATEGORIES.get(cat_key, {})
        cat_items = ui_groups.get(cat_key, {})
        if not cat_items:
            continue
        lines.extend([f'### {cat_data.get("icon", "")} {cat_data.get("label", cat_key)}', ''])
        for sub_name, items in cat_items.items():
            if not items:
                continue
            if ' (' in sub_name:
                lines.extend([f'#### {sub_name}', ''])
            lines.extend(_md_equipment_items(items))
    if sets:
        lines.extend(['### Сеты', ''])
        for set_name, set_items in sets.items():
            lines.append(f'**{set_name}**: {", ".join(set_items)}')
        lines.append('')
    return lines


def _md_equipment_items(items):
    if not items:
        return []
    lines = []
    for item in items:
        qname = _quality_name(item.get('quality', {}))
        title = item.get('title', '')
        level = item.get('level', '')
        stars = item.get('star_level', 0)
        star_str = '★' * stars + '☆' * (5 - stars) if stars > 0 else ''
        dur = item.get('durability', '')
        set_name = item.get('set', '')
        lines.append(f'**{title}** [{qname}]')
        details = []
        if level:
            details.append(f'Ур: {level}')
        if star_str:
            details.append(star_str)
        if dur:
            details.append(f'Прочность: {dur}')
        if set_name:
            details.append(f'Сет: {set_name}')
        if details:
            lines.append(f'  - {", ".join(details)}')
        skills = item.get('skills', [])
        if skills:
            lines.append('  - **Характеристики:**')
            for s in skills:
                if s.get('title'):
                    lines.append(f'    - {s["title"]}: {s.get("value", "")}')
        pattern_skills = item.get('pattern_skills', [])
        if pattern_skills:
            lines.append('  - **Характеристики узора:**')
            for s in pattern_skills:
                if s.get('title'):
                    lines.append(f'    - {s["title"]}: {s.get("value", "")}')
        stone_skills = item.get('stone_skills', [])
        if stone_skills:
            lines.append('  - **Характеристики камня:**')
            for s in stone_skills:
                if s.get('title'):
                    lines.append(f'    - {s["title"]}: {s.get("value", "")}')
        pattern = item.get('pattern', '')
        if pattern:
            lines.append(f'  - **Узор:** {_strip_html(pattern)}')
        stone = item.get('stone', '')
        if stone:
            lines.append(f'  - **Камень:** {_strip_html(stone)}')
        rune = item.get('rune', '')
        if rune:
            lines.append(f'  - **Руна:** {_strip_html(rune)}')
        rune2 = item.get('rune2', '')
        if rune2:
            lines.append(f'  - **Руна 2:** {_strip_html(rune2)}')
        runicSetting = item.get('runicSetting', '')
        if runicSetting:
            lines.append(f'  - **Руническая настройка:** {_strip_html(runicSetting)}')
        enchants = item.get('enchants', [])
        enchant_groups = _format_item_enchants(enchants)
        enchant_types = ['Оправа', 'Лак', 'Пластина', 'Встроено']
        if not stone:
            enchant_types.insert(3, 'Усиление')
        for etype in enchant_types:
            values = enchant_groups.get(etype, [])
            if values:
                lines.append(f'  - **{etype}:** {", ".join(_strip_html(v) for v in values)}')
        symbols = item.get('symbols', [])
        sym_vals = [_strip_html(s) for s in symbols if s]
        if sym_vals:
            lines.append(f'  - **Символы:** {", ".join(sym_vals)}')
        lines.append('')
    return lines


def _md_effects(data):
    lines = ['## Эффекты', '']
    perm = data.get('permanent_effects', [])
    temp = data.get('temp_effects', [])
    if perm:
        lines.extend(['### Постоянные эффекты', ''])
        for e in perm:
            lines.append(f'- **{e.get("title", "")}')
            skills = e.get('skills', [])
            if skills:
                skill_strs = [f"{s.get('title', '')}: {s.get('value', '')}" for s in skills if s.get('title')]
                if skill_strs:
                    lines.append(f'  - {", ".join(skill_strs)}')
            desc = _strip_html(e.get('desc', ''))
            if desc:
                lines.append(f'  - {desc}')
        lines.append('')
    if temp:
        by_cat = {}
        for e in temp:
            cat = e.get('category', 'other')
            by_cat.setdefault(cat, []).append(e)
        cat_labels = {'buff': 'Баффы', 'elixir': 'Эликсиры', 'mount': 'Маунты', 'debuff': 'Дебаффы', 'other': 'Прочее'}
        for cat_key in ['buff', 'elixir', 'mount', 'debuff', 'other']:
            cat_effects = by_cat.get(cat_key, [])
            if not cat_effects:
                continue
            lines.extend([f'### {cat_labels.get(cat_key, cat_key)}', ''])
            for e in cat_effects:
                time_left = e.get('time_left', '')
                time_str = f' ({time_left})' if time_left else ''
                lines.append(f'- **{e.get("title", "")}{time_str}')
                skills = e.get('skills', [])
                if skills:
                    skill_strs = [f"{s.get('title', '')}: {s.get('value', '')}" for s in skills if s.get('title')]
                    if skill_strs:
                        lines.append(f'  - {", ".join(skill_strs)}')
                desc = _strip_html(e.get('desc', ''))
                if desc:
                    lines.append(f'  - {desc}')
            lines.append('')
    return lines


def _md_medals(data):
    medals = data.get('medals', [])
    if not medals:
        return ['']
    lines = ['## Медали', '']
    by_rep = {}
    for m in medals:
        rep = m.get('reputation', 'Другие')
        by_rep.setdefault(rep, []).append(m)
    for rep, rep_medals in by_rep.items():
        lines.extend([f'### {rep}', ''])
        for m in rep_medals:
            qname = _quality_name(m.get('quality', {}))
            num = m.get('num', '')
            num_str = f' #{num}' if num else ''
            desc = _strip_html(m.get('description', ''))
            desc_str = f' — {desc}' if desc else ''
            lines.append(f'- **{m.get("title", "")}** [{qname}]{num_str}{desc_str}')
        lines.append('')
    return lines


def _md_records(data):
    records = data.get('combat_records', {})
    if not records:
        return ['']
    lines = ['## Рекорды', '', '| Рекорд | Значение |', '|--------|----------|']
    for k, v in records.items():
        lines.append(f'| {k} | {v} |')
    lines.append('')
    return lines


def _md_professions(data):
    profs = data.get('professions', {})
    if not profs:
        return ['']
    lines = ['## Профессии', '', '| Профессия | Уровень |', '|-----------|---------|']
    for k, v in profs.items():
        lines.append(f'| {k} | {v} |')
    lines.append('')
    return lines


def _md_additional(data):
    lines = ['## Дополнительно', '']
    extra = data.get('flashvars_extra', {})
    personal = data.get('personal_info', {})
    for key, label in [('hp', 'HP'), ('mp', 'MP'), ('gender', 'Пол'), ('online', 'Онлайн'), ('mount', 'Маунт'), ('town', 'Город'), ('location', 'Локация')]:
        val = extra.get(key, '')
        if val:
            lines.append(f'- **{label}:** {val}')
    for key, label in [('birthday', 'День рождения'), ('about', 'О персонаже')]:
        val = personal.get(key, '')
        if val:
            lines.append(f'- **{label}:** {_strip_html(val)}')
    manor = data.get('manor_location', '')
    if manor:
        lines.append(f'- **Усадьба:** {manor}')
    buildings = data.get('manor_buildings', [])
    if buildings:
        lines.append(f'- **Здания усадьбы:** {", ".join(buildings)}')
    lines.append('')
    return lines


# ── PDF Export ───────────────────────────────────────────────────────────────

def export_to_pdf(data, sections, page_format='landscape'):
    from weasyprint import HTML
    html_content = export_to_html(data, sections, page_format)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
