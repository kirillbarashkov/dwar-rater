import type { AnalysisResult, FlashvarsExtra } from '../../types/character';
import { StatGroup } from '../ui/StatGroup';
import { RecordsTab } from '../analysis/RecordsTab';
import './CharacterCombatTab.css';

interface CharacterCombatTabProps {
  character: AnalysisResult | null;
}

function ProgressBar({ label, current, max, color }: { label: string; current: string; max: string; color: string }) {
  const cur = parseInt(current, 10) || 0;
  const mx = parseInt(max, 10) || 1;
  const percent = Math.min(100, Math.round((cur / mx) * 100));
  return (
    <div className="char-combat-progress">
      <div className="char-combat-progress-header">
        <span className="char-combat-progress-label">{label}</span>
        <span className="char-combat-progress-value">{cur} / {mx}</span>
      </div>
      <div className="char-combat-progress-bar">
        <div className="char-combat-progress-fill" style={{ width: `${percent}%`, background: color }} />
      </div>
    </div>
  );
}

export function CharacterCombatTab({ character }: CharacterCombatTabProps) {
  if (!character) return null;

  if (character.profile_closed) {
    return (
      <div className="char-combat-tab">
        <div className="char-combat-closed-note">
          Профиль персонажа закрыт. Боевые характеристики недоступны.
        </div>
      </div>
    );
  }

  const fv: FlashvarsExtra | undefined = character.flashvars_extra;
  const hasRecords = Object.keys(character.combat_records || {}).length > 0;
  const hasGreatBattles = character.great_battles && (character.great_battles.total || character.great_battles.wins);

  return (
    <div className="char-combat-tab">
      {/* HP/MP полоски */}
      {fv && (fv.hp || fv.hpMax) && (
        <div className="char-combat-vitals">
          <ProgressBar label="❤️ Здоровье" current={fv.hp} max={fv.hpMax} color="linear-gradient(90deg, #ff5555, #ff8888)" />
          <ProgressBar label="🔵 Мана" current={fv.mp} max={fv.mpMax} color="linear-gradient(90deg, #50d4ff, #80c8ff)" />
        </div>
      )}

      {/* KPI-карточки */}
      <div className="char-combat-kpi-grid">
        <div className="char-combat-kpi-card">
          <span className="char-combat-kpi-label">Победы</span>
          <span className="char-combat-kpi-value char-combat-kpi-win">{character.wins}</span>
        </div>
        <div className="char-combat-kpi-card">
          <span className="char-combat-kpi-label">Поражения</span>
          <span className="char-combat-kpi-value char-combat-kpi-lose">{character.losses}</span>
        </div>
        <div className="char-combat-kpi-card">
          <span className="char-combat-kpi-label">Винрейт</span>
          <span className="char-combat-kpi-value">{character.winrate}%</span>
        </div>
        {character.kills && (
          <div className="char-combat-kpi-card">
            <span className="char-combat-kpi-label">Убийства</span>
            <span className="char-combat-kpi-value">{character.kills}</span>
          </div>
        )}
      </div>

      {/* Великие битвы */}
      {hasGreatBattles && (
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

      {/* Основные характеристики */}
      <StatGroup title="Основные характеристики" stats={character.main_stats} />

      {/* Боевые характеристики */}
      <StatGroup title="Боевые характеристики" stats={character.combat_stats} />

      {/* Магические характеристики */}
      <StatGroup title="Магические характеристики" stats={character.magic_stats} />

      {/* Боевые рекорды */}
      {hasRecords && (
        <RecordsTab records={character.combat_records} />
      )}
    </div>
  );
}
