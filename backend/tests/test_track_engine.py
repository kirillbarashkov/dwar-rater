"""Unit tests for the pure track engine (gap-close v2)."""
import pytest

from shared.services.track_engine import (
    compute_gaps,
    generate_steps,
    resync_progress,
    normalize_scenario,
    _parse_num,
)
from shared.config import Config


def _char(name='Hero', level=10, main=None, combat=None, magic=None, hp=1000, equipment=None, medals=None):
    return {
        'name': name,
        'level': str(level),
        'main_stats': main or {'Живучесть': '100', 'Защита': '50', 'Интуиция': '40', 'Ловкость': '30', 'Сила': '60'},
        'combat_stats': combat or {'Инициатива': '20', 'Стойкость': '15'},
        'magic_stats': magic or {'Воля': '10', 'Интеллект': '5', 'Концентрация': '8', 'Мудрость': '3', 'Подавление': '2'},
        'flashvars_extra': {'hpMax': str(hp)},
        'equipment_by_kind': equipment or {},
        'medals': medals or [],
    }


SOURCE = _char()
TARGET = _char(
    name='Target', level=12,
    main={'Живучесть': '200', 'Защита': '100', 'Интуиция': '80', 'Ловкость': '60', 'Сила': '120'},
    combat={'Инициатива': '40', 'Стойкость': '30'},
    hp=2000,
    equipment={'Оружие': [{'title': 'Меч', 'quality': 'Синий', 'star_level': 3, 'level': 5}]},
    medals=[{'num': 1, 'title': 'Заслон', 'quality': 'Синий', 'reputation': 'Гномы', 'description': ''}],
)


class TestComputeGaps:
    def test_stats_delta_pct_impact(self):
        gaps = compute_gaps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        stats = {g['stat']: g for g in gaps['stats']}
        g = stats['Живучесть']
        assert g['current'] == 100 and g['target'] == 200
        assert g['delta'] == 100 and g['pct'] == 50.0
        assert g['impact'] == pytest.approx(100 * 1.0)

    def test_combat_stats_weight(self):
        gaps = compute_gaps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        stats = {g['stat']: g for g in gaps['stats']}
        # Инициатива: 20 → 40, weight 1.8
        assert stats['Инициатива']['impact'] == pytest.approx(20 * 1.8)

    def test_hp_gap_from_flashvars(self):
        gaps = compute_gaps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        hp = gaps['hp']
        assert hp['current'] == 1000 and hp['target'] == 2000
        assert hp['impact'] == pytest.approx(1000 * 1.5)

    def test_no_gap_when_equal(self):
        gaps = compute_gaps(SOURCE, SOURCE, Config.POWER_WEIGHTS)
        assert gaps['stats'] == []
        assert gaps['hp'] is None
        assert gaps['equipment'] == []
        assert gaps['medals'] == []

    def test_equipment_gap_by_quality_and_star(self):
        src = _char(equipment={'Оружие': [{'title': 'Дубина', 'quality': 'Серый', 'star_level': 0, 'level': 1}]})
        gaps = compute_gaps(src, TARGET, Config.POWER_WEIGHTS)
        eq = {e['kind']: e for e in gaps['equipment']}
        assert 'Оружие' in eq
        assert eq['Оружие']['target_quality'] == 'Синий'
        assert eq['Оружие']['target_star'] == 3

    def test_medal_gaps_missing(self):
        gaps = compute_gaps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        titles = [m['title'] for m in gaps['medals']]
        assert 'Заслон' in titles


class TestGenerateSteps:
    def test_stable_ids(self):
        steps1, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        steps2, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        assert [s['id'] for s in steps1] == [s['id'] for s in steps2]

    def test_stat_step_id_format(self):
        steps, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        ids = [s['id'] for s in steps]
        assert 'stat:main:Живучесть' in ids
        assert 'hp:hpMax' in ids

    def test_phases_order(self):
        _, phases, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        order = [p['id'] for p in phases]
        # Only non-empty phases are built; their order must follow PHASE_ORDER
        from shared.services.track_engine import PHASE_ORDER
        assert order == [ph for ph in PHASE_ORDER if ph in order]
        assert 'level' in order and 'stats' in order and 'medals' in order

    def test_steps_sorted_by_roi_within_phase(self):
        steps, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        by_phase = {}
        for s in steps:
            by_phase.setdefault(s['phase'], []).append(s)
        for phase, group in by_phase.items():
            rois = [s['roi'] for s in group]
            assert rois == sorted(rois, reverse=True), f'phase {phase} not ROI-sorted'

    def test_step_schema(self):
        steps, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        for s in steps:
            assert set(s.keys()) >= {'id', 'type', 'phase', 'title', 'description',
                                     'priority', 'impact', 'effort', 'roi', 'current',
                                     'target', 'delta', 'pct', 'completed'}

    def test_power_gap_sum(self):
        steps, _, power_gap = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        manual = sum(s['impact'] for s in steps if not s['completed'])
        assert power_gap == pytest.approx(manual)

    def test_equipment_and_medal_steps_present(self):
        steps, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        types = {s['type'] for s in steps}
        assert 'equipment' in types
        assert 'medal' in types

    def test_medal_phase_is_medals(self):
        steps, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        medal_steps = [s for s in steps if s['type'] == 'medal']
        assert all(s['phase'] == 'medals' for s in medal_steps)


class TestResync:
    def test_auto_complete_when_reached(self):
        steps, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        grown = _char(level=12, main={'Живучесть': '250', 'Защита': '150', 'Интуиция': '100',
                            'Ловкость': '80', 'Сила': '150'},
                      combat={'Инициатива': '50', 'Стойкость': '40'},
                      hp=2500, equipment={'Оружие': [{'title': 'Меч', 'quality': 'Синий', 'star_level': 3, 'level': 5}]},
                      medals=[{'num': 1, 'title': 'Заслон', 'quality': 'Синий', 'reputation': 'Гномы', 'description': ''}])
        new_steps, _, new_gap = resync_progress(steps, grown)
        by_id = {s['id']: s for s in new_steps}
        assert by_id['stat:main:Живучесть']['completed'] is True
        assert by_id['stat:main:Живучесть']['completed_auto'] is True
        assert by_id['hp:hpMax']['completed'] is True
        assert new_gap == pytest.approx(0.0)

    def test_auto_uncompletes_manual_mark_when_current_drops(self):
        steps, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        # Manually mark a step complete even though current < target
        for s in steps:
            if s['id'] == 'stat:main:Живучесть':
                s['completed'] = True
        new_steps, _, _ = resync_progress(steps, SOURCE)  # same weak source
        by_id = {s['id']: s for s in new_steps}
        assert by_id['stat:main:Живучесть']['completed'] is False
        assert by_id['stat:main:Живучесть']['completed_auto'] is True

    def test_partial_progress_recalc(self):
        steps, _, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        grown = _char(main={'Живучесть': '150', 'Защита': '50', 'Интуиция': '40',
                            'Ловкость': '30', 'Сила': '60'})
        new_steps, _, _ = resync_progress(steps, grown)
        by_id = {s['id']: s for s in new_steps}
        s = by_id['stat:main:Живучесть']
        assert s['completed'] is False
        assert s['current'] == 150
        assert s['delta'] == 50
        assert s['pct'] == 75.0

    def test_phases_recalculated(self):
        steps, phases, _ = generate_steps(SOURCE, TARGET, Config.POWER_WEIGHTS)
        grown = _char(main={'Живучесть': '250', 'Защита': '150', 'Интуиция': '100',
                            'Ловкость': '80', 'Сила': '150'},
                      combat={'Инициатива': '50', 'Стойкость': '40'}, hp=2500)
        new_steps, new_phases, _ = resync_progress(steps, grown)
        # Все stat/hp шаги завершены; фаза stats должна быть 100%
        stats_phase = next(p for p in new_phases if p['id'] == 'stats')
        assert stats_phase['progress_pct'] == 100.0


class TestScenarioNormalization:
    def test_pseudo_character(self):
        scenario_data = {
            'target_stats': {'Живучесть': 300, 'Сила': 200},
            'recommended_equipment': [
                {'slot': 'Оружие', 'min_quality': 'Синий', 'stats': ['Сила']}
            ],
            'priority_medals': ['Заслон'],
        }
        pseudo = normalize_scenario(scenario_data)
        assert pseudo['main_stats']['Живучесть'] == 300
        assert pseudo['main_stats']['Сила'] == 200
        eq = pseudo['equipment_by_kind']['Оружие']
        assert eq[0]['quality'] == 'Синий'
        assert pseudo['medals'][0]['title'] == 'Заслон'


class TestQualityDictRegression:
    """Regression for review finding C1: processor emits quality as a
    {'name': ..., 'color': ..., 'emoji': ...} dict — the engine must not
    crash with TypeError on real (processed) character data."""

    PROC_EQUIPMENT = {
        'Оружие': [{
            'title': 'Меч', 
            'quality': {'name': 'Синий', 'color': '#3300ff', 'emoji': '🔵'},
            'star_level': 3, 'level': 5,
        }],
        'Вещи стиля': {  # nested sub-kind shape (processor.py:286-291)
            'Плащи': [{
                'title': 'Плащ',
                'quality': {'name': 'Фиолетовый', 'color': '#990099', 'emoji': '🟣'},
                'star_level': 1, 'level': 0,
            }],
        },
    }

    def _processed_char(self, equipment):
        return _char(equipment=equipment)

    def test_compute_gaps_with_processor_shaped_quality(self):
        src = self._processed_char({})
        tgt = self._processed_char(self.PROC_EQUIPMENT)
        gaps = compute_gaps(src, tgt, Config.POWER_WEIGHTS)  # must not raise
        kinds = {e['kind'] for e in gaps['equipment']}
        assert 'Оружие' in kinds
        eq = next(e for e in gaps['equipment'] if e['kind'] == 'Оружие')
        assert eq['target_quality'] == 'Синий'

    def test_style_items_nested_dict_resolved(self):
        src = self._processed_char({})
        tgt = self._processed_char(self.PROC_EQUIPMENT)
        gaps = compute_gaps(src, tgt, Config.POWER_WEIGHTS)
        kinds = {e['kind'] for e in gaps['equipment']}
        assert 'Вещи стиля' in kinds  # M1: nested sub-kind dict resolved

    def test_generate_and_resync_with_processor_shaped_data(self):
        src = self._processed_char({})
        tgt = self._processed_char(self.PROC_EQUIPMENT)
        tgt['main_stats'] = {'Живучесть': '200', 'Защита': '100', 'Интуиция': '80',
                             'Ловкость': '60', 'Сила': '120'}
        steps, _, _ = generate_steps(src, tgt, Config.POWER_WEIGHTS)
        # acquire the same equipment → equipment steps auto-complete
        grown = self._processed_char(self.PROC_EQUIPMENT)
        grown['main_stats'] = tgt['main_stats']
        new_steps, _, _ = resync_progress(steps, grown)
        equip_steps = [s for s in new_steps if s['type'] == 'equipment']
        assert equip_steps
        assert all(s['completed'] for s in equip_steps)


class TestParseNum:
    def test_formats(self):
        assert _parse_num('1 234') == 1234
        assert _parse_num('1,234') == 1234
        assert _parse_num(567) == 567
        assert _parse_num(None) == 0
        assert _parse_num('abc') == 0
