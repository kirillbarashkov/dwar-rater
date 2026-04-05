import type { Medal } from '../../types/character';
import './MedalsTab.css';

interface MedalsTabProps {
  medals: Medal[];
}

export function MedalsTab({ medals }: MedalsTabProps) {
  if (medals.length === 0) {
    return <p className="tab-placeholder">Медали не найдены</p>;
  }

  const byReputation: Record<string, Medal[]> = {};
  medals.forEach((m) => {
    const rep = m.reputation || 'Без репутации';
    if (!byReputation[rep]) byReputation[rep] = [];
    byReputation[rep].push(m);
  });

  return (
    <div className="medals-tab">
      {Object.entries(byReputation).map(([rep, repMedals]) => (
        <div key={rep} className="medal-group">
          <h3 className="medal-group-title">{rep}</h3>
          <div className="medal-list">
            {repMedals.map((medal) => (
              <div key={medal.num} className="medal-card">
                <div className="medal-header">
                  <span
                    className="medal-title"
                    style={{ color: medal.quality.color }}
                  >
                    {medal.title}
                  </span>
                  <span className="medal-num">#{medal.num}</span>
                </div>
                {medal.description && (
                  <p className="medal-desc">{medal.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
