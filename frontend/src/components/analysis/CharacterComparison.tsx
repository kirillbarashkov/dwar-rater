import { useState, useEffect } from 'react';
import { getCompareCharacters } from '../../api/compare';
import type { AnalysisResult } from '../../types/character';
import { Button } from '../ui/Button';
import './CharacterComparison.css';

interface CompareCharacter {
  id: number;
  name: string;
  data: AnalysisResult | null;
}

interface StructField {
  key: string;
  label: string;
}

interface StructSlot {
  key: string;
  label: string;
  fields: StructField[];
}

interface StructGroup {
  key: string;
  label: string;
  slots: StructSlot[];
}

function detectCombatStyle(char: AnalysisResult): string {
  const equip = char.equipment_by_kind || {};
  const mainWeapon = equip['Основное'] || [];
  const shield = equip['Легкий щит'] || [];
  
  const mainCount = mainWeapon.filter(item => item.title && item.title !== '-').length;
  const hasShield = shield.some(item => item.title && item.title !== '-');
  
  const mainStats = char.main_stats || {};
  const strength = parseInt((mainStats['Сила'] || '0').replace(/\s/g, '')) || 0;
  const agility = parseInt((mainStats['Ловкость'] || '0').replace(/\s/g, '')) || 0;
  
  if (mainCount === 0) return 'unknown';
  
  if (mainCount === 1 && !hasShield) {
    return 'костолом';
  }
  
  if (agility > strength * 1.2) {
    return 'ловкач';
  }
  
  return 'тяжеловес';
}

function getFieldValue(char: AnalysisResult, slotKey: string, fieldKey: string, isStyle: boolean = false, combatStyle?: string): string {
  if (!char.equipment_by_kind) return '-';
  
  const kindMap: Record<string, string> = {
    helmet: 'Шлем',
    bracers: 'Наручи',
    shoulderpads: 'Наплечники',
    cuirass: 'Кираса',
    greaves: 'Поножи',
    chainmail: 'Кольчуга',
    boots: 'Обувь',
    bow: 'Лук',
    quiver: 'Колчан',
    weapon_main: 'Основное',
    weapon_add: 'Двуручное',
  };
  
  const kind = kindMap[slotKey] || slotKey;
  const equip = char.equipment_by_kind || {};
  
  const styleSets = ['Мрачная жатва', 'Триумф', 'Неистовство', 'Стиль'];
  
  const isMainWeapon = slotKey === 'weapon_main';
  const isAdditionalWeapon = slotKey === 'weapon_add';
  
  let targetItem = null;
  
  if (isMainWeapon) {
    if (isStyle) {
      const mainItems = equip['Основное'] || [];
      for (const item of mainItems) {
        if (!item.set && item.title) {
          targetItem = item;
          break;
        }
      }
    } else {
      const twoHandItems = equip['Двуручное'] || [];
      const twoHandReal = twoHandItems.filter(i => i.set && i.title);
      if (twoHandReal.length > 0) {
        targetItem = twoHandReal[twoHandReal.length - 1];
      }
      if (!targetItem) {
        const mainRealItems = (equip['Основное'] || []).filter(i => i.set && i.title);
        if (mainRealItems.length > 0) {
          targetItem = mainRealItems[mainRealItems.length - 1];
        }
      }
    }
  } else if (isAdditionalWeapon) {
    if (isStyle) {
      const leftHandItems = equip['Левая рука'] || [];
      for (const item of leftHandItems) {
        if (!item.set && item.title) {
          targetItem = item;
          break;
        }
      }
      if (!targetItem) {
        const shieldItems = equip['Легкий щит'] || [];
        for (const item of shieldItems) {
          if (!item.set && item.title) {
            targetItem = item;
            break;
          }
        }
      }
    } else {
      const leftHandItems = equip['Левая рука'] || [];
      const leftHandReal = leftHandItems.filter(i => i.set && i.title);
      if (leftHandReal.length > 0) {
        targetItem = leftHandReal[leftHandReal.length - 1];
      }
      if (!targetItem) {
        const shieldItems = equip['Легкий щит'] || [];
        const shieldReal = shieldItems.filter(i => i.set && i.title);
        if (shieldReal.length > 0) {
          targetItem = shieldReal[shieldReal.length - 1];
        }
      }
      if (!targetItem) {
        const mainItems = equip['Основное'] || [];
        const mainReal = mainItems.filter(i => i.set && i.title);
        if (mainReal.length > 0) {
          targetItem = mainReal[0];
        }
      }
    }
  } else {
    const items = equip[kind] || [];
    if (!items || items.length === 0) return '-';
    
    if (targetItem === null) {
      if (isStyle) {
        for (const item of items) {
          if (!item.set && item.title) {
            targetItem = item;
            break;
          }
        }
      } else {
        for (let i = items.length - 1; i >= 0; i--) {
          if (items[i].set && items[i].title) {
            targetItem = items[i];
            break;
          }
        }
      }
    }
  }
  
  if (!targetItem) {
    const items = equip[kind] || [];
    targetItem = items[0] || null;
  }
  
  if (!targetItem) return '-';
  
  switch (fieldKey) {
    case 'title': return targetItem.title || '-';
    case 'set': return targetItem.set || '-';
    case 'rune': return targetItem.rune || '-';
    case 'runicSetting': return targetItem.runicSetting || '-';
    case 'plate': return targetItem.plate || '-';
    case 'other': return targetItem.other || '-';
    case 'lacquer': return targetItem.lacquer || '-';
    case 'symbol1': return targetItem.symbols?.[0] || '-';
    case 'symbol2': return targetItem.symbols?.[1] || '-';
    case 'symbol3': return targetItem.symbols?.[2] || '-';
    case 'symbol4': return targetItem.symbols?.[3] || '-';
    default: return '-';
  }
}

const COMMON_FIELDS: StructField[] = [
  { key: 'title', label: 'Предмет' },
  { key: 'set', label: 'Сет' },
  { key: 'rune', label: 'Руна' },
  { key: 'runicSetting', label: 'Рунная оправа' },
  { key: 'plate', label: 'Пластина' },
  { key: 'lacquer', label: 'Лак' },
  { key: 'other', label: 'Остальное' },
  { key: 'symbol1', label: 'Символ 1' },
  { key: 'symbol2', label: 'Символ 2' },
  { key: 'symbol3', label: 'Символ 3' },
];

const STRUCTURE_GROUPS: StructGroup[] = [
  {
    key: 'armor',
    label: 'Доспехи',
    slots: [
      { key: 'helmet', label: 'Шлем', fields: COMMON_FIELDS },
      { key: 'bracers', label: 'Наручи', fields: COMMON_FIELDS },
      { key: 'shoulderpads', label: 'Наплечники', fields: COMMON_FIELDS },
      { key: 'cuirass', label: 'Кираса', fields: COMMON_FIELDS },
      { key: 'greaves', label: 'Поножи', fields: COMMON_FIELDS },
      { key: 'chainmail', label: 'Кольчуга', fields: COMMON_FIELDS },
      { key: 'boots', label: 'Сапоги', fields: COMMON_FIELDS },
      { key: 'bow', label: 'Лук', fields: COMMON_FIELDS },
      { key: 'quiver', label: 'Колчан', fields: COMMON_FIELDS },
    ],
  },
  {
    key: 'weapon',
    label: 'Оружие',
    slots: [
      { key: 'weapon_main', label: 'Основное оружие', fields: COMMON_FIELDS },
      { key: 'weapon_add', label: 'Дополнительное оружие', fields: COMMON_FIELDS },
    ],
  },
  {
    key: 'style',
    label: 'Вещи стиля',
    slots: [
      { key: 'helmet', label: 'Шлем', fields: COMMON_FIELDS },
      { key: 'bracers', label: 'Наручи', fields: COMMON_FIELDS },
      { key: 'shoulderpads', label: 'Наплечники', fields: COMMON_FIELDS },
      { key: 'cuirass', label: 'Кираса', fields: COMMON_FIELDS },
      { key: 'greaves', label: 'Поножи', fields: COMMON_FIELDS },
      { key: 'chainmail', label: 'Кольчуга', fields: COMMON_FIELDS },
      { key: 'boots', label: 'Сапоги', fields: COMMON_FIELDS },
      { key: 'bow', label: 'Лук', fields: COMMON_FIELDS },
      { key: 'quiver', label: 'Колчан', fields: COMMON_FIELDS },
      { key: 'weapon_main', label: 'Основное оружие', fields: COMMON_FIELDS },
      { key: 'weapon_add', label: 'Дополнительное оружие', fields: COMMON_FIELDS },
    ],
  },
];

export function CharacterComparison() {
  const [compareChars, setCompareChars] = useState<CompareCharacter[]>([
    { id: 0, name: '', data: null },
    { id: 0, name: '', data: null },
    { id: 0, name: '', data: null },
  ]);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['armor', 'weapon', 'style']));
  const [compareList, setCompareList] = useState<CompareCharacter[]>([]);

  useEffect(() => {
    async function loadFromApi() {
      try {
        const chars = await getCompareCharacters();
        setCompareList(chars);
        const loaded = chars.slice(0, 3).map(c => ({
          id: c.id,
          name: c.name,
          data: c.data as AnalysisResult,
        }));
        while (loaded.length < 3) loaded.push({ id: 0, name: '', data: null as unknown as AnalysisResult });
        setCompareChars(loaded.slice(0, 3));
      } catch {
        // ignore
      }
    }

    loadFromApi();
  }, []);

  const handleSelectChar = async (index: number, charId: number) => {
    if (!charId) {
      setCompareChars(prev => {
        const updated = [...prev];
        updated[index] = { id: 0, name: '', data: null };
        return updated;
      });
      return;
    }

    const char = compareList.find(c => c.id === charId);
    if (!char || !char.data) return;

    setCompareChars(prev => {
      const updated = [...prev];
      updated[index] = { id: char.id, name: char.name, data: char.data };
      return updated;
    });
  };

  const toggleGroup = (key: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <div className="character-comparison">
      <div className="compare-header">
        <h3 className="compare-title">Сравнение персонажей</h3>
      </div>

      <div className="compare-selectors">
        <div className="compare-selector">
          <span className="selector-label">Персонаж (основной)</span>
          <div className="selector-wrapper">
            <select
              className="selector-select"
              value={compareChars[0].id}
              onChange={(e) => handleSelectChar(0, Number(e.target.value))}
            >
              <option value={0}>Выберите персонажа</option>
              {compareList.filter(c => c.id).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            {compareChars[0].id !== 0 && (
              <Button variant="ghost" className="selector-clear" onClick={() => handleSelectChar(0, 0)}>✕</Button>
            )}
          </div>
        </div>
        <div className="compare-selector">
          <span className="selector-label">Персонаж (доп.1)</span>
          <div className="selector-wrapper">
            <select
              className="selector-select"
              value={compareChars[1].id}
              onChange={(e) => handleSelectChar(1, Number(e.target.value))}
            >
              <option value={0}>Выберите персонажа</option>
              {compareList.filter(c => c.id).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            {compareChars[1].id !== 0 && (
              <Button variant="ghost" className="selector-clear" onClick={() => handleSelectChar(1, 0)}>✕</Button>
            )}
          </div>
        </div>
        <div className="compare-selector">
          <span className="selector-label">Персонаж (доп.2)</span>
          <div className="selector-wrapper">
            <select
              className="selector-select"
              value={compareChars[2].id}
              onChange={(e) => handleSelectChar(2, Number(e.target.value))}
            >
              <option value={0}>Выберите персонажа</option>
              {compareList.filter(c => c.id).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            {compareChars[2].id !== 0 && (
              <Button variant="ghost" className="selector-clear" onClick={() => handleSelectChar(2, 0)}>✕</Button>
            )}
          </div>
        </div>
      </div>

      <div className="compare-table-container">
        {STRUCTURE_GROUPS.map(group => (
          <div key={group.key} className="compare-group">
            <div 
              className="compare-group-header"
              onClick={() => toggleGroup(group.key)}
            >
              <span className="group-chevron">{expandedGroups.has(group.key) ? '▼' : '▶'}</span>
              <span className="group-label">{group.label}</span>
            </div>
            
            {expandedGroups.has(group.key) && (
              <div className="compare-group-content">
                {group.slots.map(slot => (
                  <div key={slot.key} className="compare-slot">
                    <div className="compare-slot-header">{slot.label}</div>
                    <table className="compare-table">
                      <thead>
                        <tr>
                          <th className="col-name">Наименование</th>
                          {compareChars.map((c, i) => (
                            <th key={i} className="col-value">{c.name || `Персонаж ${i + 1}`}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {slot.fields.map(field => (
                          <tr key={field.key}>
                            <td className="cell-label">{field.label}</td>
                            {compareChars.map((c, i) => (
                              <td key={i} className="cell-value">
                                {c.data ? getFieldValue(c.data, slot.key, field.key, group.key === 'style', detectCombatStyle(c.data)) : '-'}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}