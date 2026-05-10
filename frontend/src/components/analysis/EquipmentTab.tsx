import { useState } from 'react';
import type { EquipmentItem, EquipmentByKind } from '../../types/character';
import './EquipmentTab.css';

interface EquipmentTabProps {
  equipment?: EquipmentByKind;
  sets?: Record<string, string[]>;
}

interface SubCategory {
  key: string;
  label: string;
  kinds: string[];
}

interface EquipCategory {
  key: string;
  label: string;
  icon: string;
  priority: number;
  subCategories: SubCategory[];
}

const EQUIP_CATEGORIES: EquipCategory[] = [
  {
    key: 'combat',
    label: 'Боевая экипировка',
    icon: '🛡️',
    priority: 1,
    subCategories: [
      { key: 'combat_helmet', label: 'Шлем', kinds: ['Шлем'] },
      { key: 'combat_bracers', label: 'Наручи', kinds: ['Наручи'] },
      { key: 'combat_shoulders', label: 'Наплечники', kinds: ['Наплечники'] },
      { key: 'combat_weapon', label: 'Оружие', kinds: ['Двуручное', 'Основное', 'Левая рука', 'Легкий щит'] },
      { key: 'combat_cuirass', label: 'Кираса', kinds: ['Кираса'] },
      { key: 'combat_greaves', label: 'Поножи', kinds: ['Поножи'] },
      { key: 'combat_chainmail', label: 'Кольчуга', kinds: ['Кольчуга'] },
      { key: 'combat_boots', label: 'Обувь', kinds: ['Обувь'] },
      { key: 'combat_bow', label: 'Лук', kinds: ['Лук'] },
    ],
  },
  {
    key: 'style',
    label: 'Вещи стиля',
    icon: '🎭',
    priority: 2,
    subCategories: [
      { key: 'style_helmet', label: 'Шлем', kinds: ['Шлем'] },
      { key: 'style_bracers', label: 'Наручи', kinds: ['Наручи'] },
      { key: 'style_shoulders', label: 'Наплечники', kinds: ['Наплечники'] },
      { key: 'style_weapon', label: 'Оружие', kinds: ['Оружие'] },
      { key: 'style_cuirass', label: 'Кираса', kinds: ['Кираса'] },
      { key: 'style_greaves', label: 'Поножи', kinds: ['Поножи'] },
      { key: 'style_chainmail', label: 'Кольчуга', kinds: ['Кольчуга'] },
      { key: 'style_boots', label: 'Обувь', kinds: ['Обувь'] },
      { key: 'style_bow', label: 'Лук', kinds: ['Лук'] },
      { key: 'style_effects', label: 'Эффекты', kinds: ['Эффекты'] },
      { key: 'style_rings', label: 'Кольца', kinds: ['Кольца'] },
      { key: 'style_amulets', label: 'Амулеты', kinds: ['Амулеты'] },
    ],
  },
  {
    key: 'jewelry',
    label: 'Ювелирка',
    icon: '💍',
    priority: 3,
    subCategories: [
      { key: 'jewelry_rings', label: 'Кольца', kinds: ['Кольца'] },
      { key: 'jewelry_amulets', label: 'Амулет', kinds: ['Амулет'] },
    ],
  },
  {
    key: 'arkats',
    label: 'Аркаты',
    icon: '💠',
    priority: 4,
    subCategories: [
      { key: 'arkats_bracelet', label: 'Браслет', kinds: ['Браслет'] },
      { key: 'arkats_arkat', label: 'Аркат', kinds: ['Аркат'] },
    ],
  },
  {
    key: 'misc',
    label: 'Разное',
    icon: '📦',
    priority: 5,
    subCategories: [
      { key: 'misc_backpack', label: 'Рюкзак', kinds: ['Рюкзак'] },
      { key: 'misc_belt', label: 'Пояс', kinds: ['Пояс'] },
      { key: 'misc_craft_bag', label: 'Ремесленная сумка', kinds: ['Ремесленная сумка'] },
    ],
  },
];

function ItemCard({ item }: { item: EquipmentItem }) {
  const skills = item.skills.map(s => ({ value: `${s.title}: ${s.value}`, color: s.color }));
  const runes = item.enchants.filter(e => e.type === 'Руна' || e.type === 'Руна 2').map(e => ({ value: e.value, color: e.color }));
  const frames = item.enchants.filter(e => e.type === 'Оправа').map(e => ({ value: e.value, color: e.color }));
  const plates = item.enchants.filter(e => e.type === 'Пластина').map(e => ({ value: e.value, color: e.color }));
  const enhancements = item.enchants.filter(e => e.type === 'Усиление').map(e => ({ value: e.value, color: e.color }));
  const builtins = item.enchants.filter(e => e.type === 'Встроено').map(e => ({ value: e.value, color: e.color }));
  const symbols = item.enchants.filter(e => e.type.startsWith('Символ')).map(e => ({ value: e.value, color: e.color }));

  const stars = item.star_level > 0 ? '★'.repeat(item.star_level) + '☆'.repeat(5 - item.star_level) : '';

  const groups = [
    { title: 'ХАРАКТЕРИСТИКИ', items: skills },
    { title: 'УЗОР', items: item.pattern ? [{ value: item.pattern, color: item.quality.color }] : [] },
    { title: 'РУНА', items: runes },
    { title: 'ОПРАВА', items: frames },
    { title: 'ПЛАСТИНА', items: plates },
    { title: 'УСИЛЕНИЯ', items: enhancements },
    { title: 'СИМВОЛЫ', items: symbols },
    { title: 'ВСТРОЙКИ', items: builtins },
  ].filter(g => g.items.length > 0);

  return (
    <div className="item-card">
      <div className="item-header">
        <span className="item-title" style={{ color: item.quality.color }} title={item.title}>
          {item.title}
        </span>
        <span className="item-level">
          {stars && <span className="item-stars">{stars} </span>}
          {item.level}
        </span>
      </div>
      <div className="item-details">
        <span className="item-durability">{item.durability}</span>
        {item.set && <span className="item-set">Сет: {item.set}</span>}
      </div>
      {groups.length > 0 && (
        <div className="item-groups">
          {groups.map((group, idx) => (
            <div key={group.title} className="item-group">
              {idx > 0 && <div className="item-divider" />}
              <div className="item-group-header">{group.title}</div>
              <div className="item-group-content">
                {group.items.map((item, i) => (
                  <span
                    key={i}
                    className="item-tag"
                    style={item.color ? { color: item.color, borderColor: item.color } : undefined}
                  >
                    {item.value}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface CategoryData {
  category: EquipCategory;
  itemsBySubCategory: Map<SubCategory, EquipmentItem[]>;
  totalCount: number;
}

function mapCategories(equipment: EquipmentByKind | undefined): CategoryData[] {
  const results: CategoryData[] = [];

  for (const category of EQUIP_CATEGORIES) {
    const itemsBySubCategory = new Map<SubCategory, EquipmentItem[]>();
    let totalCount = 0;

    for (const subCat of category.subCategories) {
      const subItems: EquipmentItem[] = [];

      if (category.key === 'style') {
        const styleItems = equipment?.['Вещи стиля'];
        if (styleItems && typeof styleItems === 'object' && !Array.isArray(styleItems)) {
          for (const kind of subCat.kinds) {
            const kindItems = styleItems[kind];
            if (Array.isArray(kindItems)) {
              subItems.push(...kindItems);
            }
          }
        }
      } else {
        for (const kind of subCat.kinds) {
          const items = equipment?.[kind];
          if (Array.isArray(items)) {
            subItems.push(...items);
          }
        }
      }

      itemsBySubCategory.set(subCat, subItems);
      totalCount += subItems.length;
    }

    results.push({ category, itemsBySubCategory, totalCount });
  }

  return results.sort((a, b) => a.category.priority - b.category.priority);
}

export function EquipmentTab({ equipment, sets }: EquipmentTabProps) {
  const categories = mapCategories(equipment);
  const [activeCategory, setActiveCategory] = useState<string>('combat');
  const [activeSubFilters, setActiveSubFilters] = useState<Record<string, string>>({});

  const hasAnyItems = categories.some(c => c.totalCount > 0);
  if (!hasAnyItems && Object.keys(equipment || {}).length === 0) {
    return <p className="tab-placeholder">Экипировка не найдена</p>;
  }

  const activeCatData = categories.find(c => c.category.key === activeCategory);
  if (!activeCatData) {
    return <p className="tab-placeholder">Ошибка загрузки данных</p>;
  }

  const toggleSubFilter = (catKey: string, subKey: string) => {
    setActiveSubFilters(prev => {
      if (prev[catKey] === subKey) {
        const newFilters = { ...prev };
        delete newFilters[catKey];
        return newFilters;
      }
      return { ...prev, [catKey]: subKey };
    });
  };

  const getFilteredItems = () => {
    const activeSubFilter = activeSubFilters[activeCategory];
    if (!activeSubFilter) {
      return Array.from(activeCatData.itemsBySubCategory.values()).flat();
    }
    const subCat = activeCatData.category.subCategories.find(s => s.key === activeSubFilter);
    if (!subCat) return [];
    return activeCatData.itemsBySubCategory.get(subCat) || [];
  };

  const filteredItems = getFilteredItems();

  return (
    <div className="equipment-tab">
      <div className="equip-summary">
        {categories.map(({ category, totalCount }) => (
          <div
            key={category.key}
            className={`equip-summary-item ${activeCategory === category.key ? 'active' : ''}`}
            onClick={() => setActiveCategory(category.key)}
          >
            <span className="equip-summary-icon">{category.icon}</span>
            <span className="equip-summary-label">{category.label}</span>
            <span className="equip-summary-count">{totalCount}</span>
          </div>
        ))}
      </div>

      <div className="equip-active-category">
        <div className="equip-category-header">
          <span className="equip-category-icon">{activeCatData.category.icon}</span>
          <h2 className="equip-category-title">{activeCatData.category.label}</h2>
          <span className="equip-category-count">{activeCatData.totalCount}</span>
        </div>

        <div className="equip-subfilters">
          <button
            className={`equip-subfilter-chip ${!activeSubFilters[activeCategory] ? 'active' : ''}`}
            onClick={() => toggleSubFilter(activeCategory, '')}
          >
            Все ({activeCatData.totalCount})
          </button>
          {activeCatData.category.subCategories.map(subCat => {
            const subItems = activeCatData.itemsBySubCategory.get(subCat) || [];
            const isActive = activeSubFilters[activeCategory] === subCat.key;
            return (
              <button
                key={subCat.key}
                className={`equip-subfilter-chip ${isActive ? 'active' : ''} ${subItems.length === 0 ? 'empty' : ''}`}
                onClick={() => subItems.length > 0 && toggleSubFilter(activeCategory, subCat.key)}
                disabled={subItems.length === 0}
              >
                {subCat.label} ({subItems.length})
              </button>
            );
          })}
        </div>

        <div className="equip-grid">
          {filteredItems.map((item, i) => (
            <ItemCard key={i} item={item} />
          ))}
          {filteredItems.length === 0 && (
            <p className="equip-empty">Нет предметов в этой категории</p>
          )}
        </div>
      </div>

      {Object.keys(sets || {}).length > 0 && (
        <div className="sets-section">
          <h3 className="equip-section-title">Сетовые бонусы</h3>
          {Object.entries(sets || {}).map(([setName, items]) => (
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