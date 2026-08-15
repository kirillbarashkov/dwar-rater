"""Improvement Track v2 engine — pure gap-close logic.

No Flask dependencies: takes processed-character dicts (the shape produced
by shared/services/processor.process_character) and produces steps, phases
and power_gap. Flask-dependent target resolution (URL/snapshot/scenario
lookups) lives in normalize_target() which is called from routes with an
app context; the pure parts (compute_gaps/generate_steps/resync_progress)
are fully unit-testable.
"""

import re

POWER_WEIGHTS_DEFAULT = {
    'main_stats': {'Живучесть': 1.0, 'Сила': 2.0, 'Ловкость': 1.5,
                   'Интуиция': 1.5, 'Защита': 1.2},
    'combat_stats': {'Инициатива': 1.8, 'Стойкость': 1.3},
    'magic_stats': {'Воля': 1.0, 'Интеллект': 1.2, 'Концентрация': 1.1,
                    'Мудрость': 1.0, 'Подавление': 1.0},
    'hp': 1.5,
}
EFFORT_RANK = {'low': 1, 'medium': 2, 'high': 3}

# Numeric quality rank (processor stores quality as a color NAME string)
QUALITY_RANK = {'Серый': 0, 'Зелёный': 1, 'Синий': 2, 'Фиолетовый': 3,
                'Красный': 4, 'Оранжевый': 5, 'Легендарный': 6, 'Экзотический': 7}

PHASE_ORDER = ['level', 'reputation', 'equipment', 'stats', 'medals']
PHASE_TITLES = {
    'level': 'Уровень',
    'reputation': 'Репутация и медали',
    'equipment': 'Экипировка',
    'stats': 'Характеристики',
    'medals': 'Медали',
}
# medal steps live in the 'medals' phase but carry a reputation gate;
# level is the first gate phase; stat/hp/equipment map to their phases
PHASE_OF_TYPE = {'stat': 'stats', 'hp': 'stats', 'equipment': 'equipment',
                 'medal': 'medals', 'level': 'level', 'effect': 'stats'}


def _parse_num(val):
    """'1 234' / '1,234' / 567 / None → int (0 on garbage)."""
    try:
        return int(str(val).replace(' ', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0


# Public alias — routes import this instead of the private helper
parse_num = _parse_num


def _quality_name(q):
    """Processor stores quality as {'name': 'Синий', ...} dict; scenarios and
    tests may use a plain string. Normalize to the name string."""
    if isinstance(q, dict):
        return str(q.get('name', 'Серый'))
    return str(q) if q else 'Серый'


def _slug(text):
    return re.sub(r'[^a-zа-яё0-9]+', '-', str(text).strip().lower()).strip('-')


# ---------------------------------------------------------------------------
# Target normalization
# ---------------------------------------------------------------------------

def normalize_scenario(scenario_data):
    """LevelingScenario.scenario_data → pseudo-character dict."""
    target_stats = scenario_data.get('target_stats', {}) or {}
    main = {k: v for k, v in target_stats.items()
            if k in POWER_WEIGHTS_DEFAULT['main_stats']}
    combat = {k: v for k, v in target_stats.items()
              if k in POWER_WEIGHTS_DEFAULT['combat_stats']}
    magic = {k: v for k, v in target_stats.items()
             if k in POWER_WEIGHTS_DEFAULT['magic_stats']}

    equipment_by_kind = {}
    for eq in scenario_data.get('recommended_equipment', []) or []:
        slot = eq.get('slot', '')
        if slot:
            equipment_by_kind[slot] = [{
                'title': eq.get('title', slot),
                'quality': eq.get('min_quality', 'Серый'),
                'star_level': _parse_num(eq.get('star_level', 0)),
                'level': 0,
            }]

    medals = [{'num': i, 'title': t, 'quality': 'Серый', 'reputation': '',
               'description': ''}
              for i, t in enumerate(scenario_data.get('priority_medals', []) or [], 1)]

    return {
        'name': 'Сценарий',
        'level': str(_parse_num(target_stats.get('Уровень', 0)) or ''),
        'main_stats': main,
        'combat_stats': combat,
        'magic_stats': magic,
        'flashvars_extra': {'hpMax': target_stats.get('HP', 0)},
        'equipment_by_kind': equipment_by_kind,
        'medals': medals,
    }


# ---------------------------------------------------------------------------
# Gap computation
# ---------------------------------------------------------------------------

def compute_gaps(source, target, weights=None):
    """Compare source vs target processed characters.

    Returns {'stats': [...], 'hp': {...} | None, 'equipment': [...], 'medals': [...]}
    with only positive gaps (target ahead of source).
    """
    weights = weights or POWER_WEIGHTS_DEFAULT
    stats_gaps = []

    for group in ('main_stats', 'combat_stats', 'magic_stats'):
        src_stats = source.get(group, {}) or {}
        tgt_stats = target.get(group, {}) or {}
        group_weights = weights.get(group, {})
        for stat in tgt_stats:
            if stat not in group_weights:
                continue
            current = _parse_num(src_stats.get(stat, 0))
            target_val = _parse_num(tgt_stats[stat])
            delta = target_val - current
            if delta <= 0:
                continue
            weight = group_weights[stat]
            stats_gaps.append({
                'stat': stat, 'group': group,
                'current': current, 'target': target_val,
                'delta': delta,
                'pct': round(current / target_val * 100, 1) if target_val else 0,
                'weight': weight,
                'impact': round(delta * weight, 1),
            })

    # HP gap
    hp_gap = None
    src_hp = _parse_num((source.get('flashvars_extra') or {}).get('hpMax', 0))
    tgt_hp = _parse_num((target.get('flashvars_extra') or {}).get('hpMax', 0))
    if tgt_hp > 0 and tgt_hp > src_hp:
        hp_weight = weights.get('hp', 1.5)
        hp_gap = {
            'current': src_hp, 'target': tgt_hp, 'delta': tgt_hp - src_hp,
            'pct': round(src_hp / tgt_hp * 100, 1),
            'weight': hp_weight,
            'impact': round((tgt_hp - src_hp) * hp_weight, 1),
        }

    # Equipment gaps: per kind, best source item vs target item
    equipment_gaps = []
    src_eq = source.get('equipment_by_kind', {}) or {}
    tgt_eq = target.get('equipment_by_kind', {}) or {}
    for kind, tgt_items in tgt_eq.items():
        tgt_best = _best_item(tgt_items)
        if not tgt_best:
            continue
        src_best = _best_item(src_eq.get(kind, []))
        target_quality = _quality_name(tgt_best.get('quality', 'Серый'))
        target_star = _parse_num(tgt_best.get('star_level', 0))
        if src_best:
            src_quality = _quality_name(src_best.get('quality', 'Серый'))
            src_star = _parse_num(src_best.get('star_level', 0))
            quality_gap = QUALITY_RANK.get(target_quality, 0) - QUALITY_RANK.get(src_quality, 0)
            star_gap = target_star - src_star
            if quality_gap <= 0 and star_gap <= 0:
                continue
        equipment_gaps.append({
            'kind': kind,
            'current_title': (src_best or {}).get('title', ''),
            'current_quality': (src_best or {}).get('quality', ''),
            'current_star': _parse_num((src_best or {}).get('star_level', 0)),
            'target_title': tgt_best.get('title', ''),
            'target_quality': target_quality,
            'target_star': target_star,
        })

    # Medal gaps: target medals missing from source (by title)
    src_medal_titles = {m.get('title', '') for m in source.get('medals', []) or []}
    medal_gaps = [m for m in (target.get('medals', []) or [])
                  if m.get('title', '') and m.get('title') not in src_medal_titles]

    return {'stats': stats_gaps, 'hp': hp_gap, 'equipment': equipment_gaps, 'medals': medal_gaps}


def _best_item(items):
    """Pick the best item of a kind by (quality rank, star level).

    Understands both flat lists and the nested "Вещи стиля" shape
    ({sub_kind: [items]}). Item dicts are recognized by having a
    'title' or 'quality' key; everything else is treated as a container.
    """
    flat = []
    def _collect(node):
        if isinstance(node, list):
            for x in node:
                _collect(x)
        elif isinstance(node, dict):
            if 'title' in node or 'quality' in node:
                flat.append(node)
            else:  # container: sub-kind dict → recurse into values
                for x in node.values():
                    _collect(x)
        else:
            flat.append({'title': str(node), 'quality': 'Серый', 'star_level': 0})
    _collect(items)
    if not flat:
        return None
    return max(flat, key=lambda i: (QUALITY_RANK.get(_quality_name(i.get('quality')), 0),
                                    _parse_num(i.get('star_level', 0))))


# ---------------------------------------------------------------------------
# Step generation
# ---------------------------------------------------------------------------

def _priority_by_tertile(impact, all_impacts):
    if not all_impacts:
        return 'low'
    sorted_impacts = sorted(all_impacts)
    n = len(sorted_impacts)
    t1 = sorted_impacts[n // 3]
    t2 = sorted_impacts[2 * n // 3]
    if impact >= t2:
        return 'high'
    if impact >= t1:
        return 'medium'
    return 'low'


def generate_steps(source, target, weights=None):
    """Produce (steps, phases, power_gap) from processed source/target."""
    weights = weights or POWER_WEIGHTS_DEFAULT
    gaps = compute_gaps(source, target, weights)
    steps = []

    # Level step (phase 'level' — the first gate)
    src_level = _parse_num(source.get('level', 0))
    tgt_level = _parse_num(target.get('level', 0))
    if tgt_level > src_level > 0:
        steps.append({
            'id': 'level:lvl',
            'type': 'level',
            'phase': 'level',
            'title': f'Достичь {tgt_level} уровня',
            'description': f'Уровень: {src_level} → {tgt_level} (Δ=+{tgt_level - src_level})',
            'priority': 'medium',
            'impact': round((tgt_level - src_level) * 40, 1),
            'effort': 'high',
            'roi': 0.0,
            'current': src_level,
            'target': tgt_level,
            'delta': tgt_level - src_level,
            'pct': round(src_level / tgt_level * 100, 1) if tgt_level else 0,
            'completed': False,
            'completed_auto': False,
        })

    # Stat steps
    for g in gaps['stats']:
        steps.append({
            'id': f"stat:{g['group'].replace('_stats', '')}:{g['stat']}",
            'type': 'stat',
            'phase': 'stats',
            'title': f"Прокачать {g['stat']}",
            'description': f"{g['stat']}: {g['current']} → {g['target']} (Δ=+{g['delta']})",
            'priority': 'medium',  # re-assigned below by tertile
            'impact': g['impact'],
            'effort': 'medium',
            'roi': 0.0,  # computed below
            'current': g['current'],
            'target': g['target'],
            'delta': g['delta'],
            'pct': g['pct'],
            'completed': False,
            'completed_auto': False,
            'weight': g['weight'],
        })

    # HP step
    if gaps['hp']:
        h = gaps['hp']
        steps.append({
            'id': 'hp:hpMax',
            'type': 'hp',
            'phase': 'stats',
            'title': 'Увеличить HP',
            'description': f"HP: {h['current']} → {h['target']} (Δ=+{h['delta']})",
            'priority': 'medium',
            'impact': h['impact'],
            'effort': 'medium',
            'roi': 0.0,
            'current': h['current'],
            'target': h['target'],
            'delta': h['delta'],
            'pct': h['pct'],
            'completed': False,
            'completed_auto': False,
            'weight': h['weight'],
        })

    # Equipment steps
    for e in gaps['equipment']:
        impact = 80.0 + (QUALITY_RANK.get(e['target_quality'], 0) * 20) + e['target_star'] * 5
        effort = 'medium' if e['target_star'] >= 3 else 'low'
        steps.append({
            'id': f"equip:{e['kind']}:{e['target_quality']}:{e['target_star']}",
            'type': 'equipment',
            'phase': 'equipment',
            'title': f"Экипировка: {e['kind']}",
            'description': (f"Получить {e['target_title'] or e['kind']} "
                            f"(качество {e['target_quality']}, звёзды {e['target_star']})"),
            'priority': 'medium',
            'impact': round(impact, 1),
            'effort': effort,
            'roi': 0.0,
            'current': e['current_quality'],
            'target': {'quality': e['target_quality'], 'star_level': e['target_star'],
                       'title': e['target_title']},
            'delta': 0,
            'pct': 0,
            'completed': False,
            'completed_auto': False,
        })

    # Medal steps
    for m in gaps['medals']:
        rep = m.get('reputation', '') or ''
        steps.append({
            'id': f"medal:{_slug(rep) or 'norep'}:{_slug(m['title'])}",
            'type': 'medal',
            'phase': 'medals',
            'title': f"Медаль: {m['title']}",
            'description': (f"Получить медаль «{m['title']}»"
                            + (f" (репутация: {rep})" if rep else '')),
            'priority': 'medium',
            'impact': 50.0,
            'effort': 'high',
            'roi': 0.0,
            'current': None,
            'target': m['title'],
            'delta': 0,
            'pct': 0,
            'completed': False,
            'completed_auto': False,
        })

    # Priority by tertile of impact within the whole track
    impacts = [s['impact'] for s in steps]
    for s in steps:
        s['priority'] = _priority_by_tertile(s['impact'], impacts)
        s['roi'] = round(s['impact'] / EFFORT_RANK[s['effort']], 1)

    # Sort: phase order first, then ROI desc
    steps.sort(key=lambda s: (PHASE_ORDER.index(s['phase']), -s['roi']))

    power_gap = round(sum(s['impact'] for s in steps if not s['completed']), 1)

    phases = _build_phases(steps)
    return steps, phases, power_gap


def _build_phases(steps):
    phases = []
    for phase_id in PHASE_ORDER:
        phase_steps = [s for s in steps if s.get('phase') == phase_id]
        if not phase_steps:
            continue
        done = sum(1 for s in phase_steps if s.get('completed'))
        phases.append({
            'id': phase_id,
            'title': PHASE_TITLES[phase_id],
            'step_ids': [s['id'] for s in phase_steps],
            'progress_pct': round(done / len(phase_steps) * 100, 1),
        })
    return phases


# ---------------------------------------------------------------------------
# Re-sync (authoritative re-evaluation from a fresh source snapshot)
# ---------------------------------------------------------------------------

def _resync_level_step(step, new_source):
    current = _parse_num(new_source.get('level', 0))
    target = _parse_num(step.get('target', 0))
    step['current'] = current
    step['delta'] = max(target - current, 0)
    step['pct'] = round(current / target * 100, 1) if target else 0
    return current >= target


def _resync_stat_step(step, new_source):
    """Update a stat/hp step from the fresh source; returns True if completed."""
    if step['type'] == 'hp':
        current = _parse_num((new_source.get('flashvars_extra') or {}).get('hpMax', 0))
    else:
        stat = step['id'].split(':')[-1]
        current = _parse_num((new_source.get('main_stats', {}) or {}).get(stat, 0)
                             or (new_source.get('combat_stats', {}) or {}).get(stat, 0)
                             or (new_source.get('magic_stats', {}) or {}).get(stat, 0))
    target = _parse_num(step.get('target', 0))
    step['current'] = current
    step['delta'] = max(target - current, 0)
    step['pct'] = round(current / target * 100, 1) if target else 0
    return current >= target


def _resync_equipment_step(step, new_source):
    kind = step['id'].split(':')[1]
    target = step.get('target') or {}
    items = (new_source.get('equipment_by_kind', {}) or {}).get(kind, [])
    best = _best_item(items)
    if not best:
        step['current'] = None
        return False
    step['current'] = _quality_name(best.get('quality', 'Серый'))
    src_rank = QUALITY_RANK.get(_quality_name(best.get('quality', 'Серый')), 0)
    src_star = _parse_num(best.get('star_level', 0))
    tgt_rank = QUALITY_RANK.get(_quality_name(target.get('quality', '')), 0)
    tgt_star = _parse_num(target.get('star_level', 0))
    return src_rank >= tgt_rank and src_star >= tgt_star


def _resync_medal_step(step, new_source):
    title = step.get('target')
    titles = {m.get('title', '') for m in new_source.get('medals', []) or []}
    return bool(title and title in titles)


def resync_progress(old_steps, new_source, old_phases=None):
    """Authoritative re-sync of steps against a fresh source snapshot.

    Facts win: any step whose current value reached the target is completed
    (completed_auto=True); any step (even manually checked) below target is
    uncompleted. Returns (steps, phases, power_gap).
    """
    steps = [dict(s) for s in old_steps]
    for step in steps:
        stype = step.get('type')
        if stype in ('stat', 'hp'):
            # Legacy steps (id like 'stat_Сила') lack the 'group:' segment;
            # their resync falls back to a whole-id stat lookup that finds
            # nothing → stays uncompleted (facts-win, no crash).
            reached = _resync_stat_step(step, new_source)
        elif stype == 'equipment':
            reached = _resync_equipment_step(step, new_source)
        elif stype == 'medal':
            reached = _resync_medal_step(step, new_source)
        elif stype == 'level':
            reached = _resync_level_step(step, new_source)
        else:
            continue
        step['completed'] = reached
        step['completed_auto'] = True

    power_gap = round(sum(s['impact'] for s in steps if not s['completed']), 1)
    phases = _build_phases(steps)
    return steps, phases, power_gap
