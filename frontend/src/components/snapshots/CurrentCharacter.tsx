import type { AnalysisResult } from '../../types/character';
import './CurrentCharacter.css';

interface CurrentCharacterProps {
  character: AnalysisResult;
  lastAnalyzed: Date | null;
}

export function CurrentCharacter({ character, lastAnalyzed }: CurrentCharacterProps) {
  return (
    <div className="current-character">
      <div className="cc-name-row">
        <h3 className="cc-name">{character.name}</h3>
        <div className="cc-meta">
          {character.race && <span className="meta-tag">{character.race}</span>}
          {character.rank && <span className="meta-tag">{character.rank}</span>}
          {character.clan && <span className="meta-tag clan">{character.clan}</span>}
          {character.clan_rank && <span className="meta-tag">{character.clan_rank}</span>}
        </div>
      </div>
      <div className="cc-stats">
        <div className="cc-stat">
          <span className="cc-stat-label">Победы</span>
          <span className="cc-stat-value">{character.wins}</span>
        </div>
        <div className="cc-stat">
          <span className="cc-stat-label">Поражения</span>
          <span className="cc-stat-value">{character.losses}</span>
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
