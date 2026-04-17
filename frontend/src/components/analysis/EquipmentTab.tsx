import { useState } from 'react';
import type { EquipmentItem } from '../../types/character';
import './EquipmentTab.css';

interface EquipmentTabProps {
  equipment?: Record<string, EquipmentItem[]>;
  sets?: Record<string, string[]>;
}

interface EquipSection {
  key: string;
  label: string;
  kinds: string[];
  priority: number;
  icon: string;
}

const EQUIP_SECTIONS: EquipSection[] = [
  { key: 'armor', label: 'Доспехи', kinds: ['Кираса', 'Кольчуга', 'Шлем', 'Наплечники', 'Наручи', 'Поножи', 'Обувь'], priority: 1, icon: '🛡️' },
  { key: 'weapon', label: 'Оружие', kinds: ['Основное', 'Двуручное', 'Лук', 'Легкий щит'], priority: 2, icon: '⚔️' },
  { key: 'runes', label: 'Руны', kinds: ['Руна'], priority: 3, icon: '✨' },
  { key: 'frames', label: 'Оправы', kinds: ['Оправа'], priority: 4, icon: '💎' },
  { key: 'enhance', label: 'Заточка', kinds: ['Усиление'], priority: 5, icon: '⚡' },
  { key: 'style', label: 'Доспехи стиля', kinds: ['Вещи стиля'], priority: 6, icon: '🎭' },
  { key: 'lacquers', label: 'Лаки', kinds: ['Лак'], priority: 7, icon: '🧴' },
  { key: 'banner', label: 'Стяг', kinds: ['Знамя'], priority: 8, icon: '🚩' },
  { key: 'jewelry', label: 'Ювелирка', kinds: ['Кольца', 'Амулет', 'Медальон', 'Браслет'], priority: 9, icon: '💍' },
  { key: 'legendary', label: 'Легендарные вещи', kinds: ['Легендарный'], priority: 10, icon: '🌟' },
  { key: 'symbols', label: 'Символы', kinds: ['Магический символ', 'Символ'], priority: 11, icon: '🔯' },
  { key: 'arkats', label: 'Аркаты', kinds: ['Аркат'], priority: 12, icon: '💠' },
  { key: 'misc', label: 'Разное', kinds: [], priority: 99, icon: '📦' },
];

function ItemCard({ item }: { item: EquipmentItem }) {
  return (
    <div className="item-card">
      <div className="item-header">
        <span className="item-title" style={{ color: item.quality.color }}>
          {item.title}
        </span>
        <span className="item-level">{item.level}</span>
      </div>
      <div className="item-details">
        <span className="item-durability">{item.durability}</span>
        {item.set && <span className="item-set">Сет: {item.set}</span>}
      </div>
      {item.skills.length > 0 && (
        <div className="item-skills">
          {item.skills.map((s, i) => (
            <span key={i} className="skill-tag">{s.title}: {s.value}</span>
          ))}
        </div>
      )}
      {item.enchants.length > 0 && (
        <div className="item-enchants">
          {item.enchants.map((e, i) => (
            <span key={i} className="enchant-tag">{e.type}: {e.value}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function mapToSections(equipment: Record<string, EquipmentItem[]> | undefined): Map<EquipSection, EquipmentItem[]> {
  if (!equipment) return new Map();
  const result = new Map<EquipSection, EquipmentItem[]>();
  const misc: EquipmentItem[] = [];
  
  for (const section of EQUIP_SECTIONS) {
    const sectionItems: EquipmentItem[] = [];
    for (const kind of section.kinds) {
      if (equipment[kind]) {
        sectionItems.push(...equipment[kind]);
      }
    }
    if (sectionItems.length > 0) {
      result.set(section, sectionItems);
    }
  }
  
  for (const [kind, items] of Object.entries(equipment)) {
    if (!EQUIP_SECTIONS.some(s => s.kinds.includes(kind))) {
      misc.push(...items);
    }
  }
  
  if (misc.length > 0) {
    const miscSection = EQUIP_SECTIONS.find(s => s.key === 'misc')!;
    result.set(miscSection, misc);
  }
  
  return result;
}

export function EquipmentTab({ equipment, sets }: EquipmentTabProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  
  const sectioned = mapToSections(equipment);
  const sortedSections = Array.from(sectioned.keys()).sort((a, b) => a.priority - b.priority);
  
  const toggleCollapse = (key: string) => {
    setCollapsed(prev => ({ ...prev, [key]: !prev[key] }));
  };
  
  const toggleExpand = (key: string) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  if (sortedSections.length === 0) {
    return <p className="tab-placeholder">Экипировка не найдена</p>;
  }

  return (
    <div className="equipment-tab">
      <div className="equip-summary">
        {sortedSections.map((section) => {
          const items = sectioned.get(section)!;
          const isCollapsed = collapsed[section.key];
          return (
            <div key={section.key} className="equip-summary-item" onClick={() => toggleCollapse(section.key)}>
              <span className="equip-summary-icon">{section.icon}</span>
              <span className="equip-summary-label">{section.label}</span>
              <span className="equip-summary-count">{items.length}</span>
              <span className="equip-summary-chevron">{isCollapsed ? '▶' : '▼'}</span>
            </div>
          );
        })}
      </div>
      
      {sortedSections.map((section) => {
        const items = sectioned.get(section)!;
        const isCollapsed = collapsed[section.key];
        const isExpanded = expanded[section.key];
        const showAll = isExpanded || items.length <= 6;
        const displayItems = showAll ? items : items.slice(0, 6);
        
        return (
          <div key={section.key} className={`equip-section ${isCollapsed ? 'collapsed' : ''}`}>
            <div className="equip-section-header" onClick={() => toggleCollapse(section.key)}>
              <span className="equip-section-icon">{section.icon}</span>
              <h3 className="equip-section-title">{section.label}</h3>
              <span className="equip-section-count">{items.length}</span>
            </div>
            {!isCollapsed && (
              <div className="equip-grid">
                {displayItems.map((item, i) => (
                  <ItemCard key={i} item={item} />
                ))}
              </div>
            )}
            {!isCollapsed && items.length > 6 && (
              <button className="equip-show-more" onClick={() => toggleExpand(section.key)}>
                {isExpanded ? 'Свернуть' : `Показать еще ${items.length - 6}...`}
              </button>
            )}
          </div>
        );
      })}
      
      {Object.keys(sets).length > 0 && (
        <div className="sets-section">
          <h3 className="equip-section-title">Сетовые бонусы</h3>
          {Object.entries(sets).map(([setName, items]) => (
            <div key={setName} className="set-item">
              <span className="set-name">{setName}</span>
              <span className="set-items">{items.join(', ')}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
