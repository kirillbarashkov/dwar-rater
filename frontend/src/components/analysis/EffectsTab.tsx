import type { Effect } from '../../types/character';
import './EffectsTab.css';

interface EffectsTabProps {
  tempEffects?: Effect[];
  permanentEffects?: Effect[];
}

function EffectCard({ effect }: { effect: Effect }) {
  return (
    <div className={`effect-card effect-${effect.category || 'other'}`}>
      <div className="effect-header">
        <span className="effect-title">{effect.title}</span>
        {effect.time_left && (
          <span className="effect-time">{effect.time_left}</span>
        )}
      </div>
      {effect.skills.length > 0 && (
        <div className="effect-skills">
          {effect.skills.map((s, i) => (
            <span key={i} className="effect-skill">{s.title}: {s.value}</span>
          ))}
        </div>
      )}
      {effect.desc && (
        <p className="effect-desc">{effect.desc}</p>
      )}
    </div>
  );
}

export function EffectsTab({ tempEffects, permanentEffects }: EffectsTabProps) {
  const categories = [
    { key: 'buff', label: 'Баффы' },
    { key: 'elixir', label: 'Эликсиры' },
    { key: 'mount', label: 'Маунты' },
    { key: 'debuff', label: 'Дебаффы' },
    { key: 'other', label: 'Прочее' },
  ];

  return (
    <div className="effects-tab">
      {(permanentEffects?.length ?? 0) > 0 && (
        <div className="effects-section">
          <h3 className="effects-section-title">Постоянные эффекты</h3>
          <div className="effects-grid">
            {permanentEffects!.map((eff, i) => (
              <EffectCard key={`perm-${i}`} effect={{ ...eff, category: 'other' }} />
            ))}
          </div>
        </div>
      )}

      {(tempEffects?.length ?? 0) > 0 && (
        <div className="effects-section">
          <h3 className="effects-section-title">Временные эффекты</h3>
          {categories.map(({ key, label }) => {
            const items = (tempEffects ?? []).filter((e) => e.category === key);
            if (items.length === 0) return null;
            return (
              <div key={key} className="effect-category">
                <h4 className="effect-category-title">{label}</h4>
                <div className="effects-grid">
                  {items.map((eff, i) => (
                    <EffectCard key={`${key}-${i}`} effect={eff} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tempEffects.length === 0 && permanentEffects.length === 0 && (
        <p className="tab-placeholder">Эффекты не найдены</p>
      )}
    </div>
  );
}
