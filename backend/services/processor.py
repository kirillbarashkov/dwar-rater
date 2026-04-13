import re
from utils.formatters import clean_html, fmt_num


QUALITY_MAP = {
    '0': {'name': 'Серый', 'color': '#e0e0e0', 'emoji': '⚪'},
    '1': {'name': 'Зелёный', 'color': '#339900', 'emoji': '🟢'},
    '2': {'name': 'Синий', 'color': '#3300ff', 'emoji': '🔵'},
    '3': {'name': 'Фиолетовый', 'color': '#990099', 'emoji': '🟣'},
    '4': {'name': 'Красный', 'color': '#016e71', 'emoji': '🔴'},
    '5': {'name': 'Оранжевый', 'color': '#ff0000', 'emoji': '🟠'},
    '6': {'name': 'Уникальный', 'color': '#f55e27', 'emoji': '🌟'},
}


def format_skills(skills):
    if not skills:
        return []
    result = []
    for s in skills:
        title = s.get('title', '')
        value = clean_html(s.get('value', ''))
        result.append({'title': title, 'value': value})
    return result


def format_enchants(item):
    enchants = []
    if 'enchant' in item:
        enchants.append({'type': 'Руна', 'value': clean_html(item['enchant'].get('value', ''))})
    if 'enchant2' in item:
        enchants.append({'type': 'Руна 2', 'value': clean_html(item['enchant2'].get('value', ''))})
    if 'enchant_mod' in item:
        enchants.append({'type': 'Встроено', 'value': clean_html(item['enchant_mod'].get('value', ''))})
    if 'enchant3' in item:
        enchants.append({'type': 'Оправа', 'value': clean_html(item['enchant3'].get('value', ''))})
    if 'enchant4' in item:
        enchants.append({'type': 'Лак', 'value': clean_html(item['enchant4'].get('value', ''))})
    if 'enchant5' in item:
        enchants.append({'type': 'Усиление', 'value': clean_html(item['enchant5'].get('value', ''))})
    if 'symbols' in item:
        for i, sym in enumerate(item['symbols'], 1):
            enchants.append({'type': f'Символ {i}', 'value': clean_html(sym.get('value', ''))})
    return enchants


def _resolve_reputation(rep_name):
    if not rep_name:
        return 'Общая'

    rep_mapping = {
        'гномами небесной долины': 'Репутация гномов Небесной долины',
        'гномы небесной долины': 'Репутация гномов Небесной долины',
        'каменный лотос': 'Репутация «Каменного лотоса»',
        'хранителей красоты': 'Репутация Хранителей Красоты',
        'крадущиеся в ночи': 'Репутация «Крадущихся в ночи»',
        'вершителями судеб': 'Репутация вершителей судеб',
        'вершители судеб': 'Репутация вершителей судеб',
        'орденом подземных рыцарей': 'Репутация подземных рыцарей',
        'подземных рыцарей': 'Репутация подземных рыцарей',
        'джаггернаутов': 'Репутация Джаггернаутов',
        'джаггернауты': 'Репутация Джаггернаутов',
        'жителей мистрас': 'Репутация среди жителей Мистрас',
        'искателей мудрости': 'Репутация Искателей Мудрости',
        'великих битвах': 'Репутация участника Великих битв',
        'охотниками за нежитью': 'Репутация охотника на нежить',
        'охотники за нежитью': 'Репутация охотника на нежить',
        'охотников за нежитью': 'Репутация охотника на нежить',
        'красные топоры': 'Репутация «Красных топоров»',
        'искателями реликтов': 'Репутация искателя реликтов',
        'искатели реликтов': 'Репутация искателя реликтов',
        'искателей реликтов': 'Репутация искателя реликтов',
        'исследователями лабиринта': 'Репутация Исследователей Лабиринта',
        'флаундинов': 'Репутация Флаундинов',
        'богом мертвых и проклятых': 'Репутация бога мертвых и проклятых',
        'ловцами фортуны': 'Репутация ловцов фортуны',
        'ловцы фортуны': 'Репутация ловцов фортуны',
        'борцами с хаосом': 'Репутация борца с Хаосом',
        'борцы с хаосом': 'Репутация борца с Хаосом',
        'великим драконом': 'Репутация великого Дракона',
        'великий дракон': 'Репутация великого Дракона',
        'богиней аладеей': 'Репутация богини Аладеи',
        'богиня аладеи': 'Репутация богини Аладеи',
        'братством добродетели': 'Репутация Братства Добродетели',
        'братство добродетели': 'Репутация Братства Добродетели',
        'вершителей зла': 'Репутация вершителя Зла',
        'вершитель зла': 'Репутация вершителя Зла',
        'егеря': 'Репутация егеря',
        'мистика': 'Репутация мистика',
        'охотников за трофеями': 'Репутация Охотников за трофеями',
        'кладоискателей': 'Репутация Кладоискателей',
        'красных топоров': 'Репутация «Красных топоров»',
        'дартронга': 'Репутация Дартронга',
    }

    rep_lower = rep_name.lower()
    for key, canonical in rep_mapping.items():
        if key in rep_lower:
            return canonical

    return 'Репутация ' + rep_name[0].upper() + rep_name[1:]


def process_character(raw_data):
    if raw_data.get('profile_closed'):
        closed_info = raw_data.get('closed_info', {})
        return {
            'profile_closed': True,
            'name': raw_data['name'],
            'closed_info': {
                'level': closed_info.get('level', ''),
                'rank': closed_info.get('rank', ''),
                'picture': closed_info.get('picture', ''),
                'description': closed_info.get('description', ''),
                'premium_level': closed_info.get('premium_level', ''),
            }
}

    stats = raw_data['stats']
    wins = int(stats.get('Побед', 0))
    losses = int(stats.get('Поражений', 0))
    total = wins + losses
    wr = round(wins / total * 100, 2) if total > 0 else 0

    vb_wins = int(stats.get('Победы в Великих битвах', 0))
    vb_total = int(stats.get('Участие в Великих битвах', 0))
    vb_wr = round(vb_wins / vb_total * 100, 2) if vb_total > 0 else 0

    kill_key = 'Убито магмаров' if 'Убито магмаров' in stats else 'Убито людей'

    equipment = raw_data['equipment']
    equipment_by_kind = {}
    for item in equipment:
        kind = item.get('kind', 'Другое')
        if kind not in equipment_by_kind:
            equipment_by_kind[kind] = []

        rune_val = clean_html(item.get('enchant', {}).get('value', '')) if 'enchant' in item else ''
        rune2_val = clean_html(item.get('enchant2', {}).get('value', '')) if 'enchant2' in item else ''
        runic_val = clean_html(item.get('enchant3', {}).get('value', '')) if 'enchant3' in item else ''
        
        enchant5 = item.get('enchant5', {})
        enchant5_desc = enchant5.get('description', '') if enchant5 else ''
        if enchant5 and enchant5_desc == 'Пластина':
            plate_val = clean_html(enchant5.get('value', ''))
        else:
            plate_val = ''
        
        lacquer_val = clean_html(item.get('enchant4', {}).get('value', '')) if 'enchant4' in item else ''
        other_val = clean_html(item.get('enchant_mod', {}).get('value', '')) if 'enchant_mod' in item else ''
        symbol_vals = [clean_html(s.get('value', '')) for s in item.get('symbols', [])]

        equipment_by_kind[kind].append({
            'title': item.get('title', ''),
            'quality': QUALITY_MAP.get(item.get('quality', '0'), QUALITY_MAP['0']),
            'level': item.get('lev', {}).get('value', '—') if 'lev' in item else '—',
            'trend': item.get('trend', ''),
            'durability': f"{item.get('dur', '?')}/{item.get('dur_max', '?')}" if 'dur' in item else '∞',
            'skills': format_skills(item.get('skills', [])),
            'skills_e': format_skills(item.get('skills_e', [])),
            'enchants': format_enchants(item),
            'set': clean_html(item.get('set', {}).get('value', '')) if 'set' in item else '',
            'rune': rune_val,
            'rune2': rune2_val,
            'runicSetting': runic_val,
            'plate': plate_val,
            'lacquer': lacquer_val,
            'other': other_val,
            'symbols': symbol_vals,
            'other': '',
        })

    sets = {}
    for item in equipment:
        if 'set' in item:
            set_name = clean_html(item['set'].get('value', ''))
            if set_name not in sets:
                sets[set_name] = []
            sets[set_name].append(item.get('title', ''))

    medals = []
    for i, medal in enumerate(raw_data['medals'], 1):
        desc = medal.get('desc', '')
        rep_name = ''

        clan_match = re.search(r'class="redd">(.+?)</a>', desc)
        if not clan_match:
            clan_match = re.search(r'<a[^>]*>(.+?)</a>', desc)
        if clan_match:
            rep_name = clean_html(clan_match.group(1))

        if not rep_name:
            m = re.search(r'перед\s+(.+?)(?:\.\s|<br| и\s)', desc)
            if m:
                rep_name = clean_html(m.group(1))

        if not rep_name:
            m = re.search(r'воина\s+(?:перед\s+)?(.+?)\.\s', desc)
            if m:
                rep_name = clean_html(m.group(1))

        if not rep_name:
            m = re.search(r'заслуги\s+(.+?)(?:и\s+достижение|\.)', desc, re.DOTALL)
            if m:
                rep_name = clean_html(m.group(1))

        rep_name = re.sub(r'\.\s*Е[йё]ю\s+.*$', '', rep_name)
        rep_name = re.sub(r'\.\s*Можно\s+.*$', '', rep_name)
        rep_name = re.sub(r'\s*<br\s*/?>.*$', '', rep_name)
        rep_name = rep_name.strip()
        rep_name = re.sub(r'^(перед|воина\s+перед|заслуги\s+перед|заслуги\s+)\s*', '', rep_name)
        rep_name = re.sub(r'^(среди|расой|орденом|кланом)\s+', '', rep_name)
        rep_name = rep_name.strip('«»"\'')

        rep_name = _resolve_reputation(rep_name)

        medals.append({
            'num': i,
            'title': medal.get('title', ''),
            'quality': QUALITY_MAP.get(medal.get('quality', '0'), QUALITY_MAP['0']),
            'reputation': rep_name,
            'description': clean_html(medal.get('desc', '')),
        })

    permanent_effects = []
    for eff in raw_data.get('permanent_effects', []):
        skills = []
        for s in eff.get('skills', []):
            skills.append({
                'title': s.get('title', ''),
                'value': clean_html(s.get('value', '')),
            })
        permanent_effects.append({
            'title': eff.get('title', ''),
            'quality': QUALITY_MAP.get(eff.get('quality', '0'), QUALITY_MAP['0']),
            'skills': skills,
            'desc': clean_html(eff.get('desc', '')),
            'image': eff.get('image', ''),
        })

    temp_effects = []
    for eff in raw_data.get('temp_effects', []):
        skills = []
        for s in eff.get('skills', []):
            skills.append({
                'title': s.get('title', ''),
                'value': clean_html(s.get('value', '')),
            })

        kind_id = eff.get('kind_id', '')
        flags = int(eff.get('flags', 0)) if eff.get('flags') else 0
        del_after = eff.get('del_after_fight', 0)

        if kind_id == '65':
            if 'проклят' in eff.get('title', '').lower() or flags > 100000:
                category = 'debuff'
            else:
                category = 'buff'
        elif kind_id == '22':
            category = 'elixir'
        elif kind_id == '103':
            category = 'mount'
        else:
            category = 'other'

        temp_effects.append({
            'title': eff.get('title', ''),
            'time_left': eff.get('time_left', ''),
            'time_left_sec': int(eff.get('time_left_sec', 0)),
            'quality': QUALITY_MAP.get(eff.get('quality', '0'), QUALITY_MAP['0']),
            'skills': skills,
            'desc': clean_html(eff.get('desc', '')),
            'category': category,
            'kind_id': kind_id,
            'del_after_fight': bool(del_after),
            'picture': eff.get('picture', ''),
        })

    category_order = {'buff': 0, 'elixir': 1, 'mount': 2, 'debuff': 3, 'other': 4}
    temp_effects.sort(key=lambda e: (category_order.get(e['category'], 4), -e['time_left_sec']))

    return {
        'name': raw_data['name'],
        'race': stats.get('Раса', ''),
        'rank': stats.get('Звание', ''),
'clan': raw_data.get('clan', {}).get('Клан', '') if isinstance(raw_data.get('clan'), dict) else '',
        'clan_rank': raw_data.get('clan', {}).get('Звание', '') if isinstance(raw_data.get('clan'), dict) else '',
        'wins': fmt_num(wins),
        'losses': fmt_num(losses),
        'winrate': wr,
        'kills': fmt_num(stats.get(kill_key, 0)),
        'main_stats': {k: fmt_num(stats.get(k, 0)) for k in ['Живучесть', 'Защита', 'Интуиция', 'Ловкость', 'Сила']},
        'combat_stats': {k: fmt_num(stats.get(k, 0)) for k in ['Инициатива', 'Стойкость']},
        'magic_stats': {k: fmt_num(stats.get(k, 0)) for k in ['Воля', 'Интеллект', 'Концентрация', 'Мудрость', 'Подавление']},
        'social': {'Популярность': fmt_num(stats.get('Популярность', 0))},
        'achievements': {k: fmt_num(stats.get(k, 0)) for k in ['«Золотые Атши»', 'Сдано «Орочьих Голов»', '[Юбилейный свиток] текущий уровень', 'Подарено браслетов']},
        'great_battles': {
            'wins': fmt_num(vb_wins),
            'total': fmt_num(vb_total),
            'winrate': vb_wr,
        },
        'combat_records': {k: fmt_num(stats.get(k, 0)) for k in [
            'Максимальное количество критов', 'Максимальное количество блоков', 'Максимальный крит',
            'Максимальное количество уворотов', 'Максимальное количество смертей', 'Максимальное количество убийств',
            'Максимальное количество ударов', 'Максимально полученный крит',
            'Максимальное количество промахов', 'Максимальное количество ударов в блок',
        ]},
        'professions': raw_data.get('professions', {}),
        'equipment_by_kind': equipment_by_kind,
        'sets': sets,
        'medals': medals,
        'permanent_effects': permanent_effects,
        'temp_effects': temp_effects,
        'manor_location': raw_data.get('manor_location', ''),
        'manor_buildings': raw_data.get('manor_buildings', []),
    }
