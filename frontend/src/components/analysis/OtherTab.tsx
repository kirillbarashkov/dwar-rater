import type { AnalysisResult } from '../../types/character';
import './OtherTab.css';

interface OtherTabProps {
  character: AnalysisResult;
}

export function OtherTab({ character }: OtherTabProps) {
  const hasProfessions = Object.keys(character.professions).length > 0;

  if (!hasProfessions) {
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
    </div>
  );
}
