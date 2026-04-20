import { useState, useEffect, useCallback } from 'react';
import { getCompareCharacters, deleteCompareCharacter } from '../../api/compare';
import type { AnalysisResult } from '../../types/character';
import { Button } from '../ui/Button';
import './CharacterComparison.css';

interface CompareCharacter {
  id: number;
  name: string;
  data: AnalysisResult | null;
}

interface EquipmentItem {
  title?: string;
  set?: string;
  rune?: string;
  runicSetting?: string;
  plate?: string;
  lacquer?: string;
  other?: string;
  symbols?: string[];
  quality?: { name: string; color: string };
}

type CategoryKey = 'equipment' | 'weapon' | 'style' | 'jewelry' | 'arcane' | 'misc';

interface SlotDef {
  key: string;
  label: string;
  kind: string;
}

interface CategoryDef {
  key: CategoryKey;
  label: string;
  slots: SlotDef[];
}

const CATEGORIES: CategoryDef[] = [
  {
    key: 'equipment',
    label: 'Экипировка',
    slots: [
      { key: 'helmet', label: 'Шлем', kind: 'Шлем' },
      { key: 'bracers', label: 'Наручи', kind: 'Наручи' },
      { key: 'shoulderpads', label: 'Наплечники', kind: 'Наплечники' },
      { key: 'cuirass', label: 'Кираса', kind: 'Кираса' },
      { key: 'greaves', label: 'Поножи', kind: 'Поножи' },
      { key: 'chainmail', label: 'Кольчуга', kind: 'Кольчуга' },
      { key: 'boots', label: 'Обувь', kind: 'Обувь' },
    ],
  },
  {
    key: 'weapon',
    label: 'Оружие',
    slots: [
      { key: 'weapon_twohand', label: 'Двуручное', kind: 'Двуручное' },
      { key: 'weapon_main', label: 'Основное', kind: 'Основное' },
      { key: 'weapon_left', label: 'Левая рука', kind: 'Левая рука' },
      { key: 'shield', label: 'Легкий щит', kind: 'Легкий щит' },
    ],
  },
  {
    key: 'style',
    label: 'Вещи стиля',
    slots: [
      { key: 'style_armor', label: 'Доспехи', kind: 'Вещи стиля' },
      { key: 'style_weapon', label: 'Оружие', kind: 'Вещи стиля' },
    ],
  },
  {
    key: 'jewelry',
    label: 'Ювелирка',
    slots: [
      { key: 'ring1', label: 'Кольцо 1', kind: 'Кольцо' },
      { key: 'ring2', label: 'Кольцо 2', kind: 'Кольцо' },
      { key: 'amulet', label: 'Амулет', kind: 'Амулет' },
    ],
  },
  {
    key: 'arcane',
    label: 'Арканы',
    slots: [
      { key: 'bracelet', label: 'Браслет', kind: 'Браслет' },
      { key: 'arcane', label: 'Аркат', kind: 'Аркат' },
    ],
  },
  {
    key: 'misc',
    label: 'Разное',
    slots: [
      { key: 'belt', label: 'Пояс', kind: 'Пояс' },
      { key: 'bag', label: 'Рюкзак', kind: 'Рюкзак' },
      { key: 'craft_bag', label: 'Ремесленная сумка', kind: 'Ремесленная сумка' },
    ],
  },
];

const ITEM_FIELDS = [
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
  { key: 'symbol4', label: 'Символ 4' },
];

const STAT_LABELS = ['Уровень', 'Ранг', 'Клан', 'hp', 'mana'];

export function CharacterComparison() {
  const [compareChars, setCompareChars] = useState<CompareCharacter[]>([]);
  const [compareList, setCompareList] = useState<CompareCharacter[]>([]);
  const [activeCategory, setActiveCategory] = useState<CategoryKey>('equipment');
  const [activeSlot, setActiveSlot] = useState<string | null>(null);

  useEffect(() => {
    async function loadFromApi() {
      try {
        const chars = await getCompareCharacters();
        setCompareList(chars);
        if (chars.length > 0) {
          setActiveSlot(CATEGORIES[0].slots[0]?.key || null);
        }
      } catch {
        // ignore
      }
    }
    loadFromApi();
  }, []);

  const handleAddCharacter = useCallback((charId: number) => {
    if (compareChars.length >= 4) return;
    const char = compareList.find(c => c.id === charId);
    if (!char) return;
    setCompareChars(prev => [...prev, { id: char.id, name: char.name, data: char.data }]);
  }, [compareChars.length, compareList]);

  const handleRemoveCharacter = useCallback((index: number) => {
    setCompareChars(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleDeleteFromList = async (charId: number) => {
    try {
      await deleteCompareCharacter(charId);
      setCompareList(prev => prev.filter(c => c.id !== charId));
      setCompareChars(prev => prev.filter(c => c.id !== charId));
    } catch {
      // ignore
    }
  };

  const handleSlotSelect = useCallback((slotKey: string) => {
    setActiveSlot(slotKey);
  }, []);

  const handleCategorySelect = useCallback((catKey: CategoryKey) => {
    setActiveCategory(catKey);
    const cat = CATEGORIES.find(c => c.key === catKey);
    if (cat?.slots[0]) {
      setActiveSlot(cat.slots[0].key);
    }
  }, []);

  const getEquipmentForSlot = (char: CompareCharacter, slot: SlotDef): EquipmentItem | null => {
    if (!char.data?.equipment_by_kind) return null;
    
    const equip = char.data.equipment_by_kind;
    
    if (slot.key === 'style_armor' || slot.key === 'style_weapon') {
      const styleItems = equip['Вещи стиля'] || [];
      return styleItems[0] || null;
    }
    
    if (slot.key === 'weapon_twohand') {
      const items = equip['Двуручное'] || [];
      return items.find(i => i.set && i.title) || null;
    }
    
    if (slot.key === 'weapon_main') {
      const mainItems = (equip['Основное'] || []).filter(i => i.set && i.title);
      return mainItems[mainItems.length - 1] || null;
    }
    
    if (slot.key === 'weapon_left') {
      const items = equip['Левая рука'] || [];
      return items.find(i => i.set && i.title) || null;
    }
    
    if (slot.key === 'shield') {
      const items = equip['Легкий щит'] || [];
      return items.find(i => i.set && i.title) || null;
    }
    
    if (slot.key === 'ring1' || slot.key === 'ring2') {
      const rings = equip['Кольцо'] || [];
      const ringIndex = slot.key === 'ring1' ? 0 : 1;
      return rings[ringIndex] || null;
    }
    
    const items = equip[slot.kind] || [];
    return items.find(i => i.set && i.title) || items[0] || null;
  };

  const getFieldValue = (item: EquipmentItem | null, fieldKey: string): string => {
    if (!item) return '-';
    switch (fieldKey) {
      case 'title': return item.title || '-';
      case 'set': return item.set || '-';
      case 'rune': return item.rune || '-';
      case 'runicSetting': return item.runicSetting || '-';
      case 'plate': return item.plate || '-';
      case 'lacquer': return item.lacquer || '-';
      case 'other': return item.other || '-';
      case 'symbol1': return item.symbols?.[0] || '-';
      case 'symbol2': return item.symbols?.[1] || '-';
      case 'symbol3': return item.symbols?.[2] || '-';
      case 'symbol4': return item.symbols?.[3] || '-';
      default: return '-';
    }
  };

  const activeCategoryDef = CATEGORIES.find(c => c.key === activeCategory)!;

  const renderCharacterCard = (char: CompareCharacter, index: number) => (
    <div key={`${char.id}-${index}`} className="compare-char-card">
      <div className="compare-char-card-header">
        <div className="compare-char-card-avatar">
          {char.data?.name?.[0]?.toUpperCase() || '?'}
        </div>
        <div className="compare-char-card-info">
          <div className="compare-char-card-name">{char.name}</div>
          <div className="compare-char-card-clan">{char.data?.clan || '-'}</div>
        </div>
        <button
          className="compare-char-card-remove"
          onClick={() => handleRemoveCharacter(index)}
          aria-label="Удалить персонажа"
        >
          ×
        </button>
        <button
          className="compare-char-card-delete"
          onClick={() => handleDeleteFromList(char.id)}
          aria-label="Удалить из списка"
          title="Удалить из списка сравнения"
        >
          🗑️
        </button>
      </div>
      <div className="compare-char-card-stats">
        <div className="compare-char-card-stat">
          <span className="stat-label">Уровень</span>
          <span className="stat-value">{char.data?.main_stats?.['Уровень'] || '-'}</span>
        </div>
        <div className="compare-char-card-stat">
          <span className="stat-label">Звание</span>
          <span className="stat-value">{char.data?.rank || '-'}</span>
        </div>
      </div>
    </div>
  );

  const renderAddCharacterCard = () => (
    <div className="compare-char-card compare-char-card-add">
      <select
        className="compare-add-select"
        value=""
        onChange={(e) => {
          const val = Number(e.target.value);
          if (val) handleAddCharacter(val);
        }}
        disabled={compareChars.length >= 4}
      >
        <option value="" disabled={compareChars.length >= 4}>
          {compareChars.length >= 4 ? 'Максимум 4' : '+ Добавить'}
        </option>
        {compareList
          .filter(c => !compareChars.some(p => p.id === c.id))
          .map(c => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
      </select>
    </div>
  );

  return (
    <div className="character-comparison">
      <div className="compare-header">
        <h3 className="compare-title">Сравнение персонажей</h3>
      </div>

      <div className="compare-char-cards">
        {compareChars.length === 0 ? (
          <div className="compare-char-card compare-char-card-empty">
            <div className="compare-empty-text">
              Добавьте персонажей для сравнения
            </div>
            {renderAddCharacterCard()}
          </div>
        ) : (
          <>
            {compareChars.map(renderCharacterCard)}
            {renderAddCharacterCard()}
          </>
        )}
      </div>

      <div className="compare-category-tabs">
        {CATEGORIES.map(cat => (
          <button
            key={cat.key}
            className={`compare-category-tab ${activeCategory === cat.key ? 'compare-category-tab-active' : ''}`}
            onClick={() => handleCategorySelect(cat.key)}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <div className="compare-slot-tabs">
        {activeCategoryDef.slots.map(slot => (
          <button
            key={slot.key}
            className={`compare-slot-tab ${activeSlot === slot.key ? 'compare-slot-tab-active' : ''}`}
            onClick={() => handleSlotSelect(slot.key)}
          >
            {slot.label}
          </button>
        ))}
      </div>

      <div className="compare-slot-content">
        <div className="compare-table-wrapper">
          <table className="compare-detail-table">
            <thead>
              <tr>
                <th className="detail-col-label">Характеристика</th>
                {compareChars.length === 0 ? (
                  <th className="detail-col-empty">Добавьте персонажей</th>
                ) : (
                  compareChars.map((char, idx) => (
                    <th key={idx} className="detail-col-value">{char.name}</th>
                  ))
                )}
              </tr>
            </thead>
            <tbody>
              {ITEM_FIELDS.map(field => (
                <tr key={field.key}>
                  <td className="detail-cell-label">{field.label}</td>
                  {compareChars.length === 0 ? (
                    <td className="detail-cell-empty" colSpan={4}>-</td>
                  ) : (
                    compareChars.map((char, idx) => {
                      const slot = activeCategoryDef.slots.find(s => s.key === activeSlot);
                      const item = slot ? getEquipmentForSlot(char, slot) : null;
                      const value = getFieldValue(item, field.key);
                      return (
                        <td 
                          key={idx} 
                          className={`detail-cell-value ${value === '-' ? 'detail-cell-empty' : ''}`}
                        >
                          {value}
                        </td>
                      );
                    })
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="compare-overview-section">
        <h4 className="compare-section-title">Базовые характеристики</h4>
        <div className="compare-table-wrapper">
          <table className="compare-overview-table">
            <thead>
              <tr>
                <th className="detail-col-label">Характеристика</th>
                {compareChars.length === 0 ? (
                  <th className="detail-col-empty">Добавьте персонажей</th>
                ) : (
                  compareChars.map((char, idx) => (
                    <th key={idx} className="detail-col-value">{char.name}</th>
                  ))
                )}
              </tr>
            </thead>
            <tbody>
              {STAT_LABELS.map(stat => (
                <tr key={stat}>
                  <td className="detail-cell-label">{stat}</td>
                  {compareChars.length === 0 ? (
                    <td className="detail-cell-empty" colSpan={4}>-</td>
                  ) : (
                    compareChars.map((char, idx) => (
                      <td key={idx} className="detail-cell-value">
                        {char.data?.main_stats?.[stat] || '-'}
                      </td>
                    ))
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
