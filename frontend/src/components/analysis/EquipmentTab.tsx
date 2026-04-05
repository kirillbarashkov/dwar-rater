import type { EquipmentItem } from '../../types/character';
import './EquipmentTab.css';

interface EquipmentTabProps {
  equipment: Record<string, EquipmentItem[]>;
  sets: Record<string, string[]>;
}

function ItemCard({ item }: { item: EquipmentItem }) {
  return (
    <div className="item-card">
      <div className="item-header">
        <span
          className="item-title"
          style={{ color: item.quality.color }}
        >
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

export function EquipmentTab({ equipment, sets }: EquipmentTabProps) {
  const entries = Object.entries(equipment);

  if (entries.length === 0) {
    return <p className="tab-placeholder">Экипировка не найдена</p>;
  }

  return (
    <div className="equipment-tab">
      {entries.map(([kind, items]) => (
        <div key={kind} className="equip-section">
          <h3 className="equip-section-title">{kind}</h3>
          <div className="equip-grid">
            {items.map((item, i) => (
              <ItemCard key={i} item={item} />
            ))}
          </div>
        </div>
      ))}
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
