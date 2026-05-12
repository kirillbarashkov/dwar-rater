import re
from shared.utils.formatters import clean_html, fmt_num


QUALITY_MAP = {
    '0': {'name': 'Серый', 'color': '#e0e0e0', 'emoji': '⚪'},
    '1': {'name': 'Зелёный', 'color': '#339900', 'emoji': '🟢'},
    '2': {'name': 'Синий', 'color': '#3300ff', 'emoji': '🔵'},
    '3': {'name': 'Фиолетовый', 'color': '#990099', 'emoji': '🟣'},
    '4': {'name': 'Красный', 'color': '#016e71', 'emoji': '🔴'},
    '5': {'name': 'Оранжевый', 'color': '#ff0000', 'emoji': '🟠'},
    '6': {'name': 'Легендарный', 'color': '#f55e27', 'emoji': '🌟'},
    '7': {'name': 'Экзотический', 'color': '#f400a1', 'emoji': '💎'},
}


def extract_color_from_html(html_value):
    match = re.search(r'color:\s*([#\w]+)', html_value)
    return match.group(1) if match else None


def format_skills(skills):
    if not skills:
        return []
    result = []
    for s in skills:
        title = s.get('title', '')
        raw_value = s.get('value', '')
        value = clean_html(raw_value)
        color = extract_color_from_html(raw_value)
        item = {'title': title, 'value': value}
        if color:
            item['color'] = color
        result.append(item)
    return result


def format_enchants(item):
    enchants = []
    raw_enchant = item.get('enchant', {})
    if raw_enchant:
        raw_value = raw_enchant.get('value', '')
        enchants.append({
            'type': 'Руна',
            'value': clean_html(raw_value),
            'color': extract_color_from_html(raw_value)
        })
    raw_enchant2 = item.get('enchant2', {})
    if raw_enchant2:
        raw_value = raw_enchant2.get('value', '')
        enchants.append({
            'type': 'Руна 2',
            'value': clean_html(raw_value),
            'color': extract_color_from_html(raw_value)
        })
    raw_enchant_mod = item.get('enchant_mod', {})
    if raw_enchant_mod:
        raw_value = raw_enchant_mod.get('value', '')
        enchants.append({
            'type': 'Встроено',
            'value': clean_html(raw_value),
            'color': extract_color_from_html(raw_value)
        })
    raw_enchant3 = item.get('enchant3', {})
    if raw_enchant3:
        raw_value = raw_enchant3.get('value', '')
        enchants.append({
            'type': 'Оправа',
            'value': clean_html(raw_value),
            'color': extract_color_from_html(raw_value)
        })
    raw_enchant4 = item.get('enchant4', {})
    if raw_enchant4:
        raw_value = raw_enchant4.get('value', '')
        enchants.append({
            'type': 'Лак',
            'value': clean_html(raw_value),
            'color': extract_color_from_html(raw_value)
        })
    raw_enchant5 = item.get('enchant5', {})
    if raw_enchant5:
        raw_value = raw_enchant5.get('value', '')
        desc = raw_enchant5.get('description', '')
        enchant_type = 'Пластина' if desc == 'Пластина' else 'Усиление'
        enchants.append({
            'type': enchant_type,
            'value': clean_html(raw_value),
            'color': extract_color_from_html(raw_value)
        })
    symbols = item.get('symbols', [])
    for i, sym in enumerate(symbols, 1):
        raw_value = sym.get('value', '')
        enchants.append({
            'type': f'Символ {i}',
            'value': clean_html(raw_value),
            'color': extract_color_from_html(raw_value)
        })
    return enchants


def _parse_star_level(desc):
    """Parse star level from item description.

    Exotic items: current star has color:green, higher stars have color:808080
    Legendary items: current star has color:red, higher stars have color:808080

    Pattern: <U>N★</U> followed by color indicator
    """
    if not desc:
        return 0
    # Find all star markers with their color
    matches = re.findall(r'<U>(\d)★?</U>.*?color:([#\w]+)', desc, re.DOTALL)
    if not matches:
        return 0

    # The current star level is the LAST one that has an active color (green or red)
    # Higher levels have color:808080 (gray)
    active_colors = {'green', 'red', '008000', 'ff0000'}
    for num, color in reversed(matches):
        if color.lower() in active_colors:
            return int(num)

    # Fallback: if no active color found, return 0
    return 0


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


def _extract_quality_from_data(item_data):
    if not item_data:
        return '0'
    quality = item_data.get('quality', '0')
    return str(quality) if quality else '0'


def _extract_level_from_data(item_data):
    if not item_data:
        return '—'
    lev = item_data.get('lev', {})
    if isinstance(lev, dict):
        return lev.get('value', '—')
    return '—'


def _safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


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

    stats = raw_data.get('stats', {})

    wins = _safe_int(stats.get('Побед', 0))
    losses = _safe_int(stats.get('Поражений', 0))
    total = wins + losses
    wr = round(wins / total * 100, 2) if total > 0 else 0

    vb_wins = _safe_int(stats.get('Победы в Великих битвах', 0))
    vb_total = _safe_int(stats.get('Участие в Великих битвах', 0))
    vb_wr = round(vb_wins / vb_total * 100, 2) if vb_total > 0 else 0

    kill_key = 'Убито магмаров' if 'Убито магмаров' in stats else 'Убито людей'

    flashvars = raw_data.get('flashvars', {})

    equipment_raw = raw_data.get('equipment_raw', [])
    equipment_by_kind = {}
    sets = {}

    WEAPON_KINDS = {'Двуручное', 'Основное', 'Левая рука', 'Легкий щит'}
    STYLE_KIND_MAP = {
        'Шлем': 'Шлем',
        'Наплечники': 'Наплечники',
        'Наручи': 'Наручи',
        'Двуручное': 'Оружие',
        'Основное': 'Оружие',
        'Левая рука': 'Оружие',
        'Легкий щит': 'Оружие',
        'Кираса': 'Кираса',
        'Поножи': 'Поножи',
        'Кольчуга': 'Кольчуга',
        'Обувь': 'Обувь',
        'Лук': 'Лук',
        'Эффекты': 'Эффекты',
        'Кольца': 'Кольца',
        'Амулет': 'Амулеты',
        # Exotic items
        'Экзотическое кольцо': 'Кольца',
        'Экзотический амулет': 'Амулеты',
    }

    # Normalize exotic jewelry kinds to base kinds for UI display
    EXOTIC_TO_BASE_KIND = {
        'Экзотическое кольцо': 'Кольца',
        'Экзотический амулет': 'Амулет',
    }

    for item in equipment_raw:
        item_data = item.get('full_data', {})
        title = item_data.get('title', item.get('title', ''))
        
        item_color = item_data.get('color', '')
        is_style_item = (item_color == '#016e71')
        
        kind = item_data.get('kind', 'Другое')
        original_kind = kind
        
        # Normalize exotic jewelry to base kinds (for UI and exporter)
        kind = EXOTIC_TO_BASE_KIND.get(kind, kind)
        
        if is_style_item:
            kind = 'Вещи стиля'
        
        if kind == 'Вещи стиля':
            if kind not in equipment_by_kind:
                equipment_by_kind[kind] = {}
            style_sub_kind = STYLE_KIND_MAP.get(original_kind, original_kind)
            if style_sub_kind not in equipment_by_kind[kind]:
                equipment_by_kind[kind][style_sub_kind] = []
        elif kind not in equipment_by_kind:
            equipment_by_kind[kind] = []

        quality_str = str(item_data.get('quality', item.get('quality', '0')))

        enchant_val = item.get('enchant', '')
        enchant2_val = item.get('enchant2', '')
        enchant3_val = item.get('enchant3', '')
        enchant4_val = item.get('enchant4', '')
        enchant5_val = item.get('enchant5', '')

        enchant_data = item_data.get('enchant', {})
        enchant2_data = item_data.get('enchant2', {})
        enchant3_data = item_data.get('enchant3', {})
        enchant4_data = item_data.get('enchant4', {})
        enchant5_data = item_data.get('enchant5', {})

        enchant_mod = item_data.get('enchant_mod', {})
        symbols = item_data.get('symbols', [])

        plate_val = ''
        stone_val = ''
        if enchant5_data and isinstance(enchant5_data, dict):
            desc5 = enchant5_data.get('description', '')
            if desc5 == 'Пластина':
                plate_val = clean_html(enchant5_data.get('value', ''))
            elif desc5 == 'Драгоценный камень':
                stone_val = clean_html(enchant5_data.get('value', ''))

        # Parse star level from desc (exotic/legendary items)
        item_desc = item_data.get('desc', '')
        star_level = _parse_star_level(item_desc)

        # Parse pattern (узор) from enchant field for exotic items
        pattern_val = ''
        if enchant_data and isinstance(enchant_data, dict):
            enchant_value = clean_html(enchant_data.get('value', ''))
            if 'узор' in enchant_value.lower() or 'Узор' in enchant_value:
                pattern_val = enchant_value

        equipment_item = {
            'title': title,
            'quality': QUALITY_MAP.get(quality_str, QUALITY_MAP['0']),
            'level': _extract_level_from_data(item_data),
            'star_level': star_level,
            'pattern': pattern_val,
            'stone': stone_val,
            'trend': item_data.get('trend', ''),
            'durability': f"{item_data.get('dur', '?')}/{item_data.get('dur_max', '?')}" if 'dur' in item_data else '∞',
            'skills': format_skills(item_data.get('skills', [])),
            'skills_e': format_skills(item_data.get('skills_e', [])),
            'enchants': format_enchants(item_data),
            'set': clean_html(item_data.get('set', {}).get('value', '')) if 'set' in item_data else '',
            'rune': clean_html(enchant_val) if enchant_val and isinstance(enchant_val, str) else (clean_html(enchant_data.get('value', '')) if enchant_data else ''),
            'rune2': clean_html(enchant2_val) if enchant2_val and isinstance(enchant2_val, str) else (clean_html(enchant2_data.get('value', '')) if enchant2_data else ''),
            'runicSetting': clean_html(enchant3_val) if enchant3_val and isinstance(enchant3_val, str) else (clean_html(enchant3_data.get('value', '')) if enchant3_data else ''),
            'plate': plate_val,
            'lacquer': clean_html(enchant4_val) if enchant4_val and isinstance(enchant4_val, str) else (clean_html(enchant4_data.get('value', '')) if enchant4_data else ''),
            'other': clean_html(enchant_mod.get('value', '')) if enchant_mod else '',
            'symbols': [clean_html(s.get('value', '')) for s in symbols] if symbols else [],
            'enhancement': clean_html(enchant5_val) if enchant5_val and isinstance(enchant5_val, str) else (clean_html(enchant5_data.get('value', '')) if enchant5_data else ''),
        }

        if kind == 'Вещи стиля':
            equipment_by_kind[kind][style_sub_kind].append(equipment_item)
        else:
            equipment_by_kind[kind].append(equipment_item)

        if 'set' in item_data:
            set_name = clean_html(item_data['set'].get('value', ''))
            if set_name:
                if set_name not in sets:
                    sets[set_name] = []
                sets[set_name].append(title)

    medals_data = raw_data.get('medals', [])
    medals = []
    for i, medal in enumerate(medals_data, 1):
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
            'description': clean_html(desc),
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
            'del_after_fight': bool(eff.get('del_after_fight', 0)),
            'picture': eff.get('picture', ''),
        })

    category_order = {'buff': 0, 'elixir': 1, 'mount': 2, 'debuff': 3, 'other': 4}
    temp_effects.sort(key=lambda e: (category_order.get(e['category'], 4), -e['time_left_sec']))

    clan_data = raw_data.get('clan', {})
    clan_name = clan_data.get('Клан', '') if isinstance(clan_data, dict) else ''
    clan_rank = clan_data.get('Звание', '') if isinstance(clan_data, dict) else ''

    level_from_flashvars = flashvars.get('lvl', '')

    return {
        'name': raw_data['name'],
        'race': stats.get('Раса', ''),
        'rank': raw_data.get('rank', ''),
        'level': level_from_flashvars,
        'clan': clan_name,
        'clan_rank': clan_rank,
        'clan_id': clan_data.get('_clan_id', '') if isinstance(clan_data, dict) else '',
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
        'flashvars_extra': {
            'hp': flashvars.get('hp', ''),
            'hpMax': flashvars.get('hpMax', ''),
            'mp': flashvars.get('mp', ''),
            'mpMax': flashvars.get('mpMax', ''),
            'gender': flashvars.get('gender', ''),
            'online': flashvars.get('online', ''),
            'mount': flashvars.get('mount', ''),
            'tTown': flashvars.get('tTown', ''),
            'tLocation': flashvars.get('tLocation', ''),
        },
        'personal_info': raw_data.get('personal_info', {}),
    }
