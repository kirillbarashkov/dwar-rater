"""Character analysis exporter — generates HTML, Markdown, and PDF reports."""

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


def _strip_html(text):
    """Remove HTML tags from text."""
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()


def _quality_name(quality):
    """Get quality name from quality object or string."""
    if isinstance(quality, dict):
        return quality.get('name', '')
    return str(quality)


def _quality_color(quality):
    """Get quality color from quality object."""
    if isinstance(quality, dict):
        return quality.get('color', '#e0e0e0')
    return '#e0e0e0'


def _format_stat_group(stats):
    """Format a stat group as list of (key, value) pairs."""
    if not stats:
        return []
    return [(k, v) for k, v in stats.items()]


# ── HTML Export ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; padding: 40px 20px; }}
  .report {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); overflow: hidden; }}
  .report-header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 32px; }}
  .report-header h1 {{ font-size: 1.8rem; margin-bottom: 8px; }}
  .report-header .subtitle {{ opacity: 0.8; font-size: 0.95rem; }}
  .section {{ padding: 24px 32px; border-bottom: 1px solid #eee; }}
  .section:last-child {{ border-bottom: none; }}
  .section-title {{ font-size: 1.1rem; font-weight: 700; color: #1a1a2e; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #00d4aa; display: inline-block; }}
  .info-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }}
  .info-item {{ display: flex; flex-direction: column; }}
  .info-label {{ font-size: 0.75rem; text-transform: uppercase; color: #888; letter-spacing: 0.5px; }}
  .info-value {{ font-size: 1rem; font-weight: 500; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 0.9rem; }}
  th {{ background: #f8f9fa; font-weight: 600; color: #555; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; }}
  .quality-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }}
  .item-card {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin-bottom: 12px; border-left: 4px solid #ccc; }}
  .item-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
  .item-title {{ font-weight: 600; font-size: 1rem; }}
  .item-meta {{ font-size: 0.8rem; color: #888; }}
  .item-details {{ font-size: 0.85rem; color: #555; }}
  .item-details span {{ margin-right: 16px; }}
  .stat-group {{ margin-bottom: 16px; }}
  .stat-group h4 {{ font-size: 0.9rem; color: #555; margin-bottom: 8px; }}
  .effect-card {{ background: #f8f9fa; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; }}
  .effect-title {{ font-weight: 600; }}
  .effect-time {{ font-size: 0.8rem; color: #888; }}
  .effect-skills {{ font-size: 0.85rem; color: #555; margin-top: 4px; }}
  .medal-group {{ margin-bottom: 16px; }}
  .medal-group h4 {{ font-size: 0.9rem; color: #555; margin-bottom: 8px; }}
  .medal-item {{ padding: 4px 0; font-size: 0.9rem; }}
  .stars {{ color: #ffc857; }}
  .footer {{ padding: 16px 32px; background: #f8f9fa; text-align: center; font-size: 0.8rem; color: #888; }}
</style>
</head>
<body>
<div class="report">
{body}
</div>
</body>
</html>"""


def export_to_html(data, sections):
    """Export character analysis to HTML."""
    body_parts = []

    # Header
    name = data.get('name', 'Неизвестный')
    race = data.get('race', '')
    rank = data.get('rank', '')
    title = f'{name}' + (f' — {race}' if race else '')
    body_parts.append(f'''<div class="report-header">
<h1>{_esc(name)}</h1>
<div class="subtitle">{_esc(race)} | {_esc(rank)}</div>
</div>''')

    # Sections
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

    return HTML_TEMPLATE.format(title=_esc(title), body='\n'.join(body_parts))


def _esc(text):
    """Escape HTML special characters."""
    if not text:
        return ''
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _html_identity(data):
    items = []
    for key, label in [('race', 'Раса'), ('rank', 'Ранг'), ('level', 'Уровень'),
                        ('clan', 'Клан'), ('clan_rank', 'Роль в клане')]:
        val = data.get(key, '')
        if val:
            items.append(f'<div class="info-item"><span class="info-label">{label}</span><span class="info-value">{_esc(val)}</span></div>')
    return f'''<div class="section">
<div class="section-title">Идентификация</div>
<div class="info-grid">{''.join(items)}</div>
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
        ('Основные характеристики', data.get('main_stats', {})),
        ('Боевые характеристики', data.get('combat_stats', {})),
        ('Магические характеристики', data.get('magic_stats', {})),
        ('Социальные', data.get('social', {})),
        ('Достижения', data.get('achievements', {})),
    ]
    parts = []
    for title, stats in groups:
        if not stats:
            continue
        rows = ''.join(f'<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>' for k, v in stats.items())
        parts.append(f'<div class="stat-group"><h4>{title}</h4><table><tbody>{rows}</tbody></table></div>')
    return f'''<div class="section">
<div class="section-title">Характеристики</div>
{''.join(parts)}
</div>'''


def _html_equipment(data):
    eq_by_kind = data.get('equipment_by_kind', {})
    if not eq_by_kind:
        return ''
    parts = []
    for kind, items in eq_by_kind.items():
        if isinstance(items, dict):
            # Style items — nested
            for sub_kind, sub_items in items.items():
                parts.extend(_html_equipment_items(f'{kind} → {sub_kind}', sub_items))
        else:
            parts.extend(_html_equipment_items(kind, items))
    return f'''<div class="section">
<div class="section-title">Экипировка</div>
{''.join(parts)}
</div>'''


def _html_equipment_items(kind, items):
    if not items:
        return []
    cards = []
    for item in items:
        qname = _quality_name(item.get('quality', {}))
        qcolor = _quality_color(item.get('quality', {}))
        title = item.get('title', '')
        level = item.get('level', '')
        stars = item.get('star_level', 0)
        star_str = '<span class="stars">' + '★' * stars + '☆' * (5 - stars) + '</span>' if stars > 0 else ''
        dur = item.get('durability', '')
        set_name = item.get('set', '')
        rune = item.get('rune', '')
        plate = item.get('plate', '')

        details = []
        if level:
            details.append(f'<span>Ур: {_esc(level)}</span>')
        if star_str:
            details.append(f'<span>{star_str}</span>')
        if dur:
            details.append(f'<span>Прочность: {_esc(dur)}</span>')
        if set_name:
            details.append(f'<span>Сет: {_esc(set_name)}</span>')
        if rune:
            details.append(f'<span>Руна: {_esc(_strip_html(rune))}</span>')
        if plate:
            details.append(f'<span>Пластина: {_esc(_strip_html(plate))}</span>')

        cards.append(f'''<div class="item-card" style="border-left-color: {qcolor}">
<div class="item-header">
<span class="item-title" style="color: {qcolor}">{_esc(title)}</span>
<span class="quality-badge" style="background: {qcolor}20; color: {qcolor}">{_esc(qname)}</span>
</div>
<div class="item-details">{''.join(details)}</div>
</div>''')
    return [f'<h4 style="margin: 16px 0 8px; color: #555;">{_esc(kind)}</h4>' + ''.join(cards)]


def _html_effects(data):
    parts = []
    perm = data.get('permanent_effects', [])
    temp = data.get('temp_effects', [])
    if perm:
        cards = ''.join(f'''<div class="effect-card">
<div class="effect-title">{_esc(e.get('title', ''))}</div>
<div class="effect-skills">{_esc(e.get('desc', ''))}</div>
</div>''' for e in perm)
        parts.append(f'<div class="stat-group"><h4>Постоянные эффекты</h4>{cards}</div>')
    if temp:
        cards = ''.join(f'''<div class="effect-card">
<div class="effect-title">{_esc(e.get('title', ''))} <span class="effect-time">({_esc(e.get('time_left', ''))})</span></div>
<div class="effect-skills">{_esc(e.get('desc', ''))}</div>
</div>''' for e in temp)
        parts.append(f'<div class="stat-group"><h4>Временные эффекты</h4>{cards}</div>')
    if not parts:
        return ''
    return f'''<div class="section">
<div class="section-title">Эффекты</div>
{''.join(parts)}
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
{_esc(m.get('title', ''))}
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
    manor = data.get('manor_location', '')
    buildings = data.get('manor_buildings', [])

    for key, label in [('hp', 'HP'), ('mp', 'MP'), ('gender', 'Пол'), ('online', 'Онлайн'), ('mount', 'Маунт'), ('town', 'Город'), ('location', 'Локация')]:
        val = extra.get(key, '')
        if val:
            items.append(f'<div class="info-item"><span class="info-label">{label}</span><span class="info-value">{_esc(val)}</span></div>')
    for key, label in [('birthday', 'День рождения'), ('about', 'О персонаже')]:
        val = personal.get(key, '')
        if val:
            items.append(f'<div class="info-item"><span class="info-label">{label}</span><span class="info-value">{_esc(_strip_html(val))}</span></div>')
    if manor:
        items.append(f'<div class="info-item"><span class="info-label">Усадьба</span><span class="info-value">{_esc(manor)}</span></div>')
    if buildings:
        items.append(f'<div class="info-item"><span class="info-label">Здания усадьбы</span><span class="info-value">{_esc(", ".join(buildings))}</span></div>')
    if not items:
        return ''
    return f'''<div class="section">
<div class="section-title">Дополнительно</div>
<div class="info-grid">{''.join(items)}</div>
</div>'''


# ── Markdown Export ──────────────────────────────────────────────────────────

def export_to_markdown(data, sections):
    """Export character analysis to Markdown."""
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
    lines.append(f'')
    lines.append(f'*Dwar Rater — {now}*')
    return '\n'.join(lines)


def _md_identity(data):
    lines = ['## Идентификация', '']
    for key, label in [('race', 'Раса'), ('rank', 'Ранг'), ('level', 'Уровень'),
                        ('clan', 'Клан'), ('clan_rank', 'Роль в клане')]:
        val = data.get(key, '')
        if val:
            lines.append(f'- **{label}:** {val}')
    lines.append('')
    return lines


def _md_combat_stats(data):
    lines = ['## Боевая статистика', '']
    lines.append('| Параметр | Значение |')
    lines.append('|----------|----------|')
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
    groups = [
        ('Основные характеристики', data.get('main_stats', {})),
        ('Боевые характеристики', data.get('combat_stats', {})),
        ('Магические характеристики', data.get('magic_stats', {})),
        ('Социальные', data.get('social', {})),
        ('Достижения', data.get('achievements', {})),
    ]
    for title, stats in groups:
        if not stats:
            continue
        lines.append(f'### {title}')
        lines.append('')
        lines.append('| Характеристика | Значение |')
        lines.append('|----------------|----------|')
        for k, v in stats.items():
            lines.append(f'| {k} | {v} |')
        lines.append('')
    return lines


def _md_equipment(data):
    eq_by_kind = data.get('equipment_by_kind', {})
    if not eq_by_kind:
        return []
    lines = ['## Экипировка', '']
    for kind, items in eq_by_kind.items():
        if isinstance(items, dict):
            for sub_kind, sub_items in items.items():
                lines.extend(_md_equipment_items(f'{kind} → {sub_kind}', sub_items))
        else:
            lines.extend(_md_equipment_items(kind, items))
    return lines


def _md_equipment_items(kind, items):
    if not items:
        return []
    lines = [f'### {kind}', '']
    for item in items:
        qname = _quality_name(item.get('quality', {}))
        title = item.get('title', '')
        level = item.get('level', '')
        stars = item.get('star_level', 0)
        star_str = '★' * stars + '☆' * (5 - stars) if stars > 0 else ''
        dur = item.get('durability', '')
        set_name = item.get('set', '')
        rune = _strip_html(item.get('rune', ''))
        plate = _strip_html(item.get('plate', ''))

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
        if rune:
            details.append(f'Руна: {rune}')
        if plate:
            details.append(f'Пластина: {plate}')
        if details:
            lines.append(f'  - {", ".join(details)}')
        lines.append('')
    return lines


def _md_effects(data):
    lines = ['## Эффекты', '']
    perm = data.get('permanent_effects', [])
    temp = data.get('temp_effects', [])
    if perm:
        lines.append('### Постоянные эффекты')
        lines.append('')
        for e in perm:
            lines.append(f'- **{_esc_md(e.get("title", ""))}**')
            desc = _strip_html(e.get('desc', ''))
            if desc:
                lines.append(f'  - {desc}')
        lines.append('')
    if temp:
        lines.append('### Временные эффекты')
        lines.append('')
        for e in temp:
            time_left = e.get('time_left', '')
            lines.append(f'- **{_esc_md(e.get("title", ""))}** ({time_left})')
            desc = _strip_html(e.get('desc', ''))
            if desc:
                lines.append(f'  - {desc}')
        lines.append('')
    return lines


def _esc_md(text):
    """Escape Markdown special characters in text."""
    if not text:
        return ''
    return str(text).replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]')


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
        lines.append(f'### {rep}')
        lines.append('')
        for m in rep_medals:
            qname = _quality_name(m.get('quality', {}))
            lines.append(f'- **{m.get("title", "")}** [{qname}]')
        lines.append('')
    return lines


def _md_records(data):
    records = data.get('combat_records', {})
    if not records:
        return ['']
    lines = ['## Рекорды', '']
    lines.append('| Рекорд | Значение |')
    lines.append('|--------|----------|')
    for k, v in records.items():
        lines.append(f'| {k} | {v} |')
    lines.append('')
    return lines


def _md_professions(data):
    profs = data.get('professions', {})
    if not profs:
        return ['']
    lines = ['## Профессии', '']
    lines.append('| Профессия | Уровень |')
    lines.append('|-----------|---------|')
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

def export_to_pdf(data, sections):
    """Export character analysis to PDF via WeasyPrint."""
    from weasyprint import HTML
    html_content = export_to_html(data, sections)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
