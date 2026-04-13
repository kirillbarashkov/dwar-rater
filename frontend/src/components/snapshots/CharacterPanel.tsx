import { useState } from 'react';
import type { AnalysisResult } from '../../types/character';
import { Button } from '../ui/Button';
import { SearchBar } from '../layout/SearchBar';
import { CurrentCharacter } from './CurrentCharacter';

interface CharacterPanelProps {
  character?: AnalysisResult;
  lastAnalyzed: Date | null;
  onAnalyze: (url: string) => void;
  isLoading: boolean;
  onSave: () => void;
  onClear: () => void;
  onAddToCompare: () => void;
  defaultExpanded?: boolean;
}

export function CharacterPanel({ 
  character, 
  lastAnalyzed, 
  onAnalyze, 
  isLoading,
  onSave, 
  onClear, 
  onAddToCompare, 
  defaultExpanded = true 
}: CharacterPanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [url, setUrl] = useState('');

  const handleAnalyze = () => {
    if (url.trim()) {
      onAnalyze(url.trim());
    }
  };

  return (
    <div className={`character-panel ${expanded ? 'expanded' : 'collapsed'}`}>
      <div className="character-panel-header">
        <div className="cph-left">
          <SearchBar 
            onAnalyze={onAnalyze} 
            isLoading={isLoading} 
            compact={!expanded} 
            value={url} 
            onChange={setUrl} 
          />
        </div>
        <div className="cph-actions">
          <Button 
            variant="primary" 
            onClick={handleAnalyze} 
            disabled={isLoading || !url.trim()}
          >
            Анализировать персонажа
          </Button>
          <Button 
            variant="primary" 
            onClick={onSave} 
            disabled={!character}
          >
            Сохранить слепок
          </Button>
          <Button 
            variant="primary" 
            onClick={onAddToCompare}
            disabled={!character}
          >
            Добавить к сравнению
          </Button>
          <Button 
            variant="primary" 
            onClick={onClear}
          >
            Очистить поле
          </Button>
        </div>
        <div 
          className="cph-toggle" 
          onClick={() => setExpanded(!expanded)}
          role="button"
          tabIndex={0}
          aria-expanded={expanded}
        >
          <span className="cph-toggle-icon">{expanded ? '▼' : '▶'}</span>
          <span className="cph-toggle-text">
            {expanded ? 'Свернуть' : 'Развернуть'}
          </span>
        </div>
      </div>
      <div className="character-panel-body">
        {character ? (
          <CurrentCharacter
            character={character}
            lastAnalyzed={lastAnalyzed}
          />
        ) : expanded && (
          <div className="cph-placeholder">
            Введите ссылку на персонажа dwar.ru для анализа
          </div>
        )}
      </div>
    </div>
  );
}