import type { AnalysisResult } from '../../types/character';
import './OtherTab.css';

interface OtherTabProps {
  character: AnalysisResult;
}

export function OtherTab({ character }: OtherTabProps) {
  const hasProfessions = Object.keys(character.professions).length > 0;
  const hasManor = character.manor_location || character.manor_buildings.length > 0;

  if (!hasProfessions && !hasManor) {
    return <p className="tab-placeholder">Дополнительная информация не найдена</p>;
  }

  return (
    <div className="other-tab">
      {hasProfessions && (
        <div className="stat-group">
          <h3 className="stat-group-title">Профессии</h3>
          <table className="stat-table">
            <tbody>
              {Object.entries(character.professions).map(([key, value]) => (
                <tr key={key}>
                  <td className="stat-label">{key}</td>
                  <td className="stat-value">{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasManor && (
        <div className="stat-group">
          <h3 className="stat-group-title">Особняк</h3>
          {character.manor_location && (
            <table className="stat-table">
              <tbody>
                <tr>
                  <td className="stat-label">Расположение</td>
                  <td className="stat-value">{character.manor_location}</td>
                </tr>
              </tbody>
            </table>
          )}
          {character.manor_buildings.length > 0 && (
            <div className="manor-buildings">
              {character.manor_buildings.map((b, i) => (
                <span key={i} className="building-tag">{b}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
