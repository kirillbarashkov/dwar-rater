import { useEffect, useState } from 'react';
import type { AnalysisResult } from '../../types/character';
import type { Snapshot } from '../../types/snapshot';
import { getSnapshots } from '../../api/snapshots';
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
  onLoadSnapshot: (data: Snapshot & Record<string, unknown>) => void;
  defaultExpanded?: boolean;
}

type SourceMode = 'url' | 'snapshot';

export function CharacterPanel({
  character,
  lastAnalyzed,
  onAnalyze,
  isLoading,
  onSave,
  onClear,
  onAddToCompare,
  onLoadSnapshot,
  defaultExpanded = true
}: CharacterPanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [url, setUrl] = useState('');
  const [sourceMode, setSourceMode] = useState<SourceMode>('url');
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [snapId, setSnapId] = useState('');
  const [snapLoading, setSnapLoading] = useState(false);

  // Load the snapshot list lazily, once the user switches to snapshot mode
  useEffect(() => {
    if (sourceMode !== 'snapshot' || snapshots.length > 0 || snapLoading) return;
    setSnapLoading(true);
    getSnapshots({ page: 1, per_page: 100 })
      .then((res) => setSnapshots(res.snapshots))
      .catch(() => setSnapshots([]))
      .finally(() => setSnapLoading(false));
  }, [sourceMode, snapshots.length, snapLoading]);

  const handleAnalyze = () => {
    if (url.trim()) {
      onAnalyze(url.trim());
    }
  };

  const handleLoadSnapshot = async () => {
    if (!snapId) return;
    const { getSnapshot } = await import('../../api/snapshots');
    try {
      const data = await getSnapshot(Number(snapId));
      onLoadSnapshot(data);
    } catch {
      // snapshot may have been deleted — refresh the list
      setSnapshots([]);
      setSnapId('');
    }
  };

  const handleClear = () => {
    setUrl('');
    setSnapId('');
    onClear();
  };

  return (
    <div className={`character-panel ${expanded ? 'expanded' : 'collapsed'}`}>
      <div className="character-panel-header">
        <div className="cph-left">
          <div className="cph-source-modes">
            <label className={`cph-mode ${sourceMode === 'url' ? 'active' : ''}`}>
              <input
                type="radio"
                name="cph-source"
                checked={sourceMode === 'url'}
                onChange={() => setSourceMode('url')}
              />
              Ссылка
            </label>
            <label className={`cph-mode ${sourceMode === 'snapshot' ? 'active' : ''}`}>
              <input
                type="radio"
                name="cph-source"
                checked={sourceMode === 'snapshot'}
                onChange={() => setSourceMode('snapshot')}
              />
              Снапшот
            </label>
          </div>
          {sourceMode === 'url' ? (
            <SearchBar
              onAnalyze={onAnalyze}
              isLoading={isLoading}
              compact={!expanded}
              value={url}
              onChange={setUrl}
            />
          ) : (
            <div className="cph-snapshot-select">
              <select
                className="cph-select"
                value={snapId}
                onChange={(e) => setSnapId(e.target.value)}
                disabled={snapLoading}
              >
                <option value="">
                  {snapLoading ? 'Загрузка снапшотов…' : 'Выберите снапшот'}
                </option>
                {snapshots.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nick || s.name} ({new Date(s.analyzed_at).toLocaleDateString('ru')})
                  </option>
                ))}
              </select>
              <Button
                variant="primary"
                onClick={handleLoadSnapshot}
                disabled={isLoading || !snapId}
              >
                Загрузить
              </Button>
            </div>
          )}
        </div>
        <div className="cph-actions">
          <Button
            variant="primary"
            onClick={handleAnalyze}
            disabled={isLoading || sourceMode !== 'url' || !url.trim()}
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
            onClick={handleClear}
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
            {sourceMode === 'url'
              ? 'Введите ссылку на персонажа dwar.ru для анализа'
              : 'Выберите сохранённый снапшот персонажа'}
          </div>
        )}
      </div>
    </div>
  );
}
