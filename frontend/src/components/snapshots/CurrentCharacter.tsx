import type { AnalysisResult } from '../../types/character';
import './CurrentCharacter.css';

interface CurrentCharacterProps {
  character: AnalysisResult;
  lastAnalyzed: Date | null;
  onClear: () => void;
}

export function CurrentCharacter({ character, lastAnalyzed, onClear }: CurrentCharacterProps) {
  return (
    <div className="current-character">
      <div className="cc-header">
        <div className="cc-info">
          <h3 className="cc-name">{character.name}</h3>
          <div className="cc-meta">
            {character.race && <span>{character.race}</span>}
            {character.rank && <span>{character.rank}</span>}
            {character.clan && <span className="cc-clan">{character.clan}</span>}
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClear}>
          Очистить
        </button>
      </div>
      <div className="cc-stats">
        <div className="cc-stat">
          <span className="cc-stat-label">Победы</span>
          <span className="cc-stat-value">{character.wins}</span>
        </div>
        <div className="cc-stat">
          <span className="cc-stat-label">Винрейт</span>
          <span className="cc-stat-value winrate">{character.winrate}%</span>
        </div>
        <div className="cc-stat">
          <span className="cc-stat-label">Убийства</span>
          <span className="cc-stat-value">{character.kills}</span>
        </div>
      </div>
      {lastAnalyzed && (
        <p className="cc-analyzed">
          Последняя проверка: {lastAnalyzed.toLocaleString('ru-RU')}
        </p>
      )}
    </div>
  );
}
