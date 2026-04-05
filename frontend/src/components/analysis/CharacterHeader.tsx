import type { AnalysisResult } from '../../types/character';
import './CharacterHeader.css';

interface CharacterHeaderProps {
  character: AnalysisResult;
}

export function CharacterHeader({ character }: CharacterHeaderProps) {
  return (
    <div className="character-header">
      <div className="char-info">
        <h2 className="char-name">{character.name}</h2>
        <div className="char-meta">
          {character.race && <span className="meta-tag">{character.race}</span>}
          {character.rank && <span className="meta-tag">{character.rank}</span>}
          {character.clan && <span className="meta-tag clan">{character.clan}</span>}
          {character.clan_rank && <span className="meta-tag">{character.clan_rank}</span>}
        </div>
      </div>
      <div className="char-combat">
        <div className="combat-stat">
          <span className="combat-label">Победы</span>
          <span className="combat-value">{character.wins}</span>
        </div>
        <div className="combat-stat">
          <span className="combat-label">Поражения</span>
          <span className="combat-value">{character.losses}</span>
        </div>
        <div className="combat-stat">
          <span className="combat-label">Винрейт</span>
          <span className="combat-value winrate">{character.winrate}%</span>
        </div>
        <div className="combat-stat">
          <span className="combat-label">Убийства</span>
          <span className="combat-value">{character.kills}</span>
        </div>
      </div>
    </div>
  );
}
