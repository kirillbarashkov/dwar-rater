import { useState, useEffect, useCallback } from 'react';
import { getCompareCharacters, deleteCompareCharacter } from '../../api/compare';
import type { AnalysisResult } from '../../types/character';
import { Button } from '../ui/Button';
import './CompareListManager.css';

interface CompareCharacter {
  id: number;
  name: string;
  data: AnalysisResult;
  added_at: string;
  sort_order: number;
}

export function CompareListManager() {
  const [characters, setCharacters] = useState<CompareCharacter[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showConfirm, setShowConfirm] = useState(false);

  const loadCharacters = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getCompareCharacters();
      setCharacters(data);
    } catch {
      setCharacters([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCharacters();
  }, [loadCharacters]);

  const handleDelete = async (id: number) => {
    try {
      await deleteCompareCharacter(id);
      setCharacters(prev => prev.filter(c => c.id !== id));
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch {
      // ignore
    }
  };

  const handleDeleteSelected = async () => {
    for (const id of selectedIds) {
      try {
        await deleteCompareCharacter(id);
      } catch {
        // ignore
      }
    }
    setCharacters(prev => prev.filter(c => !selectedIds.has(c.id)));
    setSelectedIds(new Set());
    setShowConfirm(false);
  };

  const handleSelectAll = () => {
    if (selectedIds.size === characters.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(characters.map(c => c.id)));
    }
  };

  const handleToggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  if (isLoading) {
    return <div className="compare-list-loading">Загрузка...</div>;
  }

  return (
    <div className="compare-list-manager">
      <div className="compare-list-header">
        <div className="compare-list-title-row">
          <h3 className="compare-list-title">Мой список сравнения</h3>
          <span className="compare-list-count">{characters.length} персонажей</span>
        </div>
        {characters.length > 0 && (
          <div className="compare-list-actions">
            <Button 
              variant="secondary" 
              size="small"
              onClick={handleSelectAll}
            >
              {selectedIds.size === characters.length ? 'Снять выделение' : 'Выбрать все'}
            </Button>
            <Button 
              variant="danger" 
              size="small"
              disabled={selectedIds.size === 0}
              onClick={() => setShowConfirm(true)}
            >
              Удалить выбранные ({selectedIds.size})
            </Button>
          </div>
        )}
      </div>

      {characters.length === 0 ? (
        <div className="compare-list-empty">
          <div className="compare-list-empty-icon">📋</div>
          <div className="compare-list-empty-text">Список сравнения пуст</div>
          <div className="compare-list-empty-hint">
            Персонажи добавляются при сохранении слепка или через вкладку "Сравнить персонажей"
          </div>
        </div>
      ) : (
        <div className="compare-list-table-wrapper">
          <table className="compare-list-table">
            <thead>
              <tr>
                <th className="col-select"></th>
                <th className="col-name">Персонаж</th>
                <th className="col-level">Уровень</th>
                <th className="col-clan">Клан</th>
                <th className="col-date">Добавлен</th>
                <th className="col-actions"></th>
              </tr>
            </thead>
            <tbody>
              {characters.map(char => (
                <tr 
                  key={char.id} 
                  className={selectedIds.has(char.id) ? 'row-selected' : ''}
                >
                  <td className="col-select">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(char.id)}
                      onChange={() => handleToggleSelect(char.id)}
                      className="compare-list-checkbox"
                    />
                  </td>
                  <td className="col-name">
                    <div className="compare-list-name-cell">
                      <span className="compare-list-avatar">
                        {char.data?.name?.[0]?.toUpperCase() || '?'}
                      </span>
                      <span className="compare-list-name">{char.name}</span>
                    </div>
                  </td>
                  <td className="col-level">
                    {char.data?.main_stats?.['Уровень'] || '-'}
                  </td>
                  <td className="col-clan">
                    {char.data?.clan || '-'}
                  </td>
                  <td className="col-date">
                    {formatDate(char.added_at)}
                  </td>
                  <td className="col-actions">
                    <button
                      className="compare-list-delete-btn"
                      onClick={() => handleDelete(char.id)}
                      title="Удалить"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showConfirm && (
        <div className="compare-list-modal-overlay" onClick={() => setShowConfirm(false)}>
          <div className="compare-list-modal" onClick={e => e.stopPropagation()}>
            <div className="compare-list-modal-title">Удалить выбранных?</div>
            <div className="compare-list-modal-text">
              Будет удалено {selectedIds.size} персонажей из списка сравнения.
              Это действие нельзя отменить.
            </div>
            <div className="compare-list-modal-actions">
              <Button variant="secondary" onClick={() => setShowConfirm(false)}>
                Отмена
              </Button>
              <Button variant="danger" onClick={handleDeleteSelected}>
                Удалить
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
