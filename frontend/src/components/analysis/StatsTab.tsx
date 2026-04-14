import type { AnalysisResult } from '../../types/character';
import './StatsTab.css';

interface StatsTabProps {
  character: AnalysisResult;
}

function StatGroup({ title, stats }: { title: string; stats?: Record<string, string> }) {
  if (!stats) return null;
  const entries = Object.entries(stats);
  if (entries.length === 0) return null;

  return (
    <div className="stat-group">
      <h3 className="stat-group-title">{title}</h3>
      <table className="stat-table">
        <tbody>
          {entries.map(([key, value]) => (
            <tr key={key}>
              <td className="stat-label">{key}</td>
              <td className="stat-value">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StatsTab({ character }: StatsTabProps) {
  return (
    <div className="stats-tab">
      <StatGroup title="Основные" stats={character.main_stats} />
      <StatGroup title="Боевые" stats={character.combat_stats} />
      <StatGroup title="Магические" stats={character.magic_stats} />
      <StatGroup title="Социальные" stats={character.social} />
      <StatGroup title="Достижения" stats={character.achievements} />
      {character.great_battles && (
        <div className="stat-group">
          <h3 className="stat-group-title">Великие битвы</h3>
          <table className="stat-table">
            <tbody>
              <tr>
                <td className="stat-label">Победы</td>
                <td className="stat-value">{character.great_battles.wins}</td>
              </tr>
              <tr>
                <td className="stat-label">Участие</td>
                <td className="stat-value">{character.great_battles.total}</td>
              </tr>
              <tr>
                <td className="stat-label">Винрейт</td>
                <td className="stat-value">{character.great_battles.winrate}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
