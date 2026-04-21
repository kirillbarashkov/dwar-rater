import { useState, useEffect, useCallback } from 'react';
import { getCompareCharacters, deleteCompareCharacter } from '../../api/compare';
import { getClanInfo } from '../../api/clanInfo';
import type { AnalysisResult, EquipmentItem } from '../../types/character';
import './CharacterComparison.css';

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
  const lacquers = item.enchants.filter(e => e.type === 'Лак').map(e => ({ value: e.value, color: e.color }));
  const builtins = item.enchants.filter(e => e.type === 'Встроено').map(e => ({ value: e.value, color: e.color }));
  const symbols = item.enchants.filter(e => e.type.startsWith('Символ')).map(e => ({ value: e.value, color: e.color }));

  const groups = [
    { title: 'ХАРАКТЕРИСТИКИ', items: skills },
    { title: 'РУНА', items: runes },
    { title: 'ОПРАВА', items: frames },
    { title: 'УСИЛЕНИЯ', items: lacquers },
    { title: 'СИМВОЛЫ', items: symbols },
    { title: 'ВСТРОЙКИ', items: builtins },
  ].filter(g => g.items.length > 0);

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
      {groups.length > 0 && (
        <div className="item-groups">
          {groups.map((group, idx) => (
            <div key={group.title} className="item-group">
              {idx > 0 && <div className="item-divider" />}
              <div className="item-group-header">{group.title}</div>
              <div className="item-group-content">
                {group.items.map((it, i) => (
                  <span
                    key={i}
                    className="item-tag"
                    style={it.color ? { color: it.color, borderColor: it.color } : undefined}
                  >
                    {it.value}
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

interface ApiCompareCharacter {
  id: number;
  name: string;
  data: AnalysisResult;
  added_at: string;
  sort_order: number;
}

interface SelectedCharacter {
  id: number;
  name: string;
  data: AnalysisResult | null;
}

function getItemsForCharacter(charData: AnalysisResult | null, subCat: SubCategory): EquipmentItem[] {
  if (!charData?.equipment_by_kind) return [];
  const equip = charData.equipment_by_kind;
  const subItems: EquipmentItem[] = [];

  const isStyle = subCat.key.startsWith('style_');

  for (const kind of subCat.kinds) {
    if (isStyle) {
      const styleItems = equip['Вещи стиля'];
      if (styleItems && typeof styleItems === 'object' && !Array.isArray(styleItems)) {
        const kindItems = styleItems[kind];
        if (Array.isArray(kindItems)) {
          subItems.push(...kindItems);
        }
      }
    } else {
      const items = equip[kind];
      if (Array.isArray(items)) {
        subItems.push(...items);
      }
    }
  }

  return subItems;
}

export function CharacterComparison() {
  const [compareChars, setCompareChars] = useState<SelectedCharacter[]>([]);
  const [compareList, setCompareList] = useState<ApiCompareCharacter[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>('combat');
  const [activeSubFilters, setActiveSubFilters] = useState<Record<string, string>>({});
  const [clanLogos, setClanLogos] = useState<Record<string, string>>({});

  useEffect(() => {
    async function loadFromApi() {
      try {
        const chars = await getCompareCharacters();
        setCompareList(chars);

        // Load clan logos for characters with clan_id
        const uniqueClanIds = new Set<string>();
        chars.forEach(c => {
          const cid = c.data?.clan_id;
          if (cid && cid !== '0' && cid !== '') {
            uniqueClanIds.add(cid);
          }
        });

        const logos: Record<string, string> = {};
        await Promise.all(
          Array.from(uniqueClanIds).map(async (clanIdStr) => {
            try {
              const clanId = Number(clanIdStr);
              if (!isNaN(clanId) && clanId > 0) {
                const info = await getClanInfo(clanId);
                if (info.logo_small || info.logo_url) {
                  logos[clanIdStr] = info.logo_small || info.logo_url;
                }
              }
            } catch {
              // ignore clan load errors
            }
          })
        );
        setClanLogos(logos);
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
    if (compareChars.some(c => c.id === charId)) return;
    setCompareChars(prev => [...prev, { id: char.id, name: char.name, data: char.data }]);
  }, [compareChars.length, compareList, compareChars]);

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

  const activeCatData = EQUIP_CATEGORIES.find(c => c.key === activeCategory);

  const getCategoryCount = (category: EquipCategory) => {
    let count = 0;
    for (const char of compareChars) {
      for (const subCat of category.subCategories) {
        count += getItemsForCharacter(char.data, subCat).length;
      }
    }
    return count;
  };

  const handleCategorySelect = useCallback((catKey: string) => {
    setActiveCategory(catKey);
  }, []);

  return (
    <div className="character-comparison">
      <div className="compare-header">
        <h3 className="compare-title">Сравнение персонажей</h3>
      </div>

      <div className="compare-char-selector">
        {compareChars.length === 0 && (
          <div className="compare-char-card compare-char-card-empty">
            <div className="compare-empty-text">Добавьте персонажей для сравнения</div>
          </div>
        )}
        {compareChars.map((char, index) => {
          const clanLogo = char.data?.clan_id ? clanLogos[char.data.clan_id] : null;
          return (
            <div key={`${char.id}-${index}`} className="compare-char-card">
              <div className="compare-char-card-header">
                <div className={`compare-char-card-avatar ${clanLogo ? 'has-logo' : ''}`}>
                  {clanLogo ? (
                    <img src={clanLogo} alt={char.data?.clan || ''} className="compare-char-card-avatar-img" />
                  ) : (
                    char.data?.name?.[0]?.toUpperCase() || '?'
                  )}
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
                  <span className="stat-value">{char.data?.level || char.data?.main_stats?.['Уровень'] || '-'}</span>
                </div>
                <div className="compare-char-card-stat">
                  <span className="stat-label">Звание</span>
                  <span className="stat-value">{char.data?.rank || '-'}</span>
                </div>
              </div>
            </div>
          );
        })}
        <div className="compare-char-card compare-char-card-add">
          <select
            className="compare-add-select"
            value=""
            onChange={(e) => {
              const val = Number(e.target.value);
              if (val) handleAddCharacter(val);
            }}
            disabled={compareChars.length >= 4 || compareList.filter(c => !compareChars.some(p => p.id === c.id)).length === 0}
          >
            <option value="" disabled>
              {compareChars.length >= 4 ? 'Максимум 4' : '+ Добавить'}
            </option>
            {compareList
              .filter(c => !compareChars.some(p => p.id === c.id))
              .map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
          </select>
        </div>
      </div>

      {compareChars.length > 0 && (
        <div className="equipment-tab">
          <div className="equip-summary">
            {EQUIP_CATEGORIES.map(category => {
              const count = getCategoryCount(category);
              return (
                <div
                  key={category.key}
                  className={`equip-summary-item ${activeCategory === category.key ? 'active' : ''}`}
                  onClick={() => handleCategorySelect(category.key)}
                >
                  <span className="equip-summary-icon">{category.icon}</span>
                  <span className="equip-summary-label">{category.label}</span>
                  <span className="equip-summary-count">{count}</span>
                </div>
              );
            })}
          </div>

          {activeCatData && (
            <div className="equip-active-category">
              <div className="equip-category-header">
                <span className="equip-category-icon">{activeCatData.icon}</span>
                <h2 className="equip-category-title">{activeCatData.label}</h2>
                <span className="equip-category-count">{getCategoryCount(activeCatData)}</span>
              </div>

              <div className="equip-subfilters">
                <button
                  className={`equip-subfilter-chip ${!activeSubFilters[activeCategory] ? 'active' : ''}`}
                  onClick={() => toggleSubFilter(activeCategory, '')}
                >
                  Все
                </button>
                {activeCatData.subCategories.map(subCat => {
                  const hasItems = compareChars.some(char => getItemsForCharacter(char.data, subCat).length > 0);
                  return (
                    <button
                      key={subCat.key}
                      className={`equip-subfilter-chip ${activeSubFilters[activeCategory] === subCat.key ? 'active' : ''} ${!hasItems ? 'empty' : ''}`}
                      onClick={() => hasItems && toggleSubFilter(activeCategory, subCat.key)}
                      disabled={!hasItems}
                    >
                      {subCat.label}
                    </button>
                  );
                })}
              </div>

              <div className="compare-equip-content">
                {activeSubFilters[activeCategory] ? (
                  (() => {
                    const subCat = activeCatData.subCategories.find(s => s.key === activeSubFilters[activeCategory]);
                    if (!subCat) return null;
                    const hasItems = compareChars.some(char => getItemsForCharacter(char.data, subCat).length > 0);
                    if (!hasItems) return <p className="equip-empty">Нет предметов в этом слоте</p>;
                    return (
                      <div className="compare-slot-section">
                        <h4 className="compare-slot-title">{subCat.label}</h4>
                        <div className="compare-slot-row">
                          {compareChars.map(char => {
                            const items = getItemsForCharacter(char.data, subCat);
                            return (
                              <div key={char.id} className="compare-char-slot">
                                <div className="compare-char-slot-header">{char.name}</div>
                                {items.length > 0 ? (
                                  items.map((item, i) => <ItemCard key={i} item={item} />)
                                ) : (
                                  <div className="compare-empty-slot">—</div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()
                ) : (
                  activeCatData.subCategories.map(subCat => {
                    const hasItems = compareChars.some(char => getItemsForCharacter(char.data, subCat).length > 0);
                    if (!hasItems) return null;
                    return (
                      <div key={subCat.key} className="compare-slot-section">
                        <h4 className="compare-slot-title">{subCat.label}</h4>
                        <div className="compare-slot-row">
                          {compareChars.map(char => {
                            const items = getItemsForCharacter(char.data, subCat);
                            return (
                              <div key={char.id} className="compare-char-slot">
                                <div className="compare-char-slot-header">{char.name}</div>
                                {items.length > 0 ? (
                                  items.map((item, i) => <ItemCard key={i} item={item} />)
                                ) : (
                                  <div className="compare-empty-slot">—</div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
