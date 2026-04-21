import { useState, useEffect } from 'react';
import type { Snapshot } from '../../types/snapshot';
import { getSnapshots, clearCache } from '../../api/snapshots';
import { SnapshotCard } from './SnapshotCard';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { useAuth } from '../../hooks/useAuth';
import { showToast } from '../ui/Toast';
import './SnapshotHistory.css';

interface SnapshotHistoryProps {
  onLoad: (snapshot: Snapshot & Record<string, unknown>) => void;
}

export function SnapshotHistory({ onLoad }: SnapshotHistoryProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [totalPages, setTotalPages] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasFetched, setHasFetched] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showGroupDelete, setShowGroupDelete] = useState(false);
  const [cacheSelectedNicks, setCacheSelectedNicks] = useState<Set<string>>(new Set());
  const [isClearingCache, setIsClearingCache] = useState(false);

  useEffect(() => {
    if (!hasFetched) {
      loadSnapshots(1, '');
    }
  }, []);

  const loadSnapshots = async (p: number, s: string) => {
    setIsLoading(true);
    try {
      const data = await getSnapshots({ page: p, per_page: 10, nick: s || undefined });
      setSnapshots(data.snapshots);
      setTotalPages(data.pages);
      setHasFetched(true);
    } catch {
      setSnapshots([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadSnapshots(1, search);
  };

  const handleLoad = async (id: number) => {
    try {
      const { getSnapshot } = await import('../../api/snapshots');
      const data = await getSnapshot(id);
      onLoad(data);
    } catch {
      // ignore
    }
  };

  const handleDeleteClick = (id: number) => {
    setDeleteId(id);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteId && deleteId !== -1) return;
    try {
      const { deleteSnapshot } = await import('../../api/snapshots');
      if (deleteId === -1) {
        for (const s of snapshots) {
          await deleteSnapshot(s.id);
        }
      } else {
        await deleteSnapshot(deleteId);
      }
      setDeleteId(null);
      loadSnapshots(page, search);
    } catch {
      setDeleteId(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteId(null);
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

  const handleSelectAll = () => {
    if (selectedIds.size === snapshots.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(snapshots.map(s => s.id)));
    }
  };

  const handleGroupDeleteClick = () => {
    setShowGroupDelete(true);
  };

  const handleGroupDeleteConfirm = async () => {
    if (selectedIds.size === 0) return;
    try {
      const { deleteSnapshot } = await import('../../api/snapshots');
      for (const id of selectedIds) {
        await deleteSnapshot(id);
      }
      setSelectedIds(new Set());
      setShowGroupDelete(false);
      loadSnapshots(page, search);
    } catch {
      setShowGroupDelete(false);
    }
  };

  const handleGroupDeleteCancel = () => {
    setShowGroupDelete(false);
    setSelectedIds(new Set());
  };

  const handleToggleCacheNick = (nick: string) => {
    setCacheSelectedNicks(prev => {
      const next = new Set(prev);
      if (next.has(nick)) {
        next.delete(nick);
      } else {
        next.add(nick);
      }
      return next;
    });
  };

  const handleClearCache = async () => {
    if (!isAdmin) return;
    setIsClearingCache(true);
    try {
      if (cacheSelectedNicks.size > 0) {
        let cleared = 0;
        let notFound = 0;
        for (const nick of cacheSelectedNicks) {
          try {
            const result = await clearCache(nick);
            if (result.message.includes('не найден')) {
              notFound++;
            } else {
              cleared++;
            }
          } catch {
            notFound++;
          }
        }
        showToast(`Очищено: ${cleared}, не найдено: ${notFound}`, 'success');
      } else {
        const result = await clearCache();
        showToast(result.message, 'success');
      }
      setCacheSelectedNicks(new Set());
    } catch {
      showToast('Ошибка при очистке кэша', 'error');
    } finally {
      setIsClearingCache(false);
    }
  };

  if (!hasFetched) {
    return (
      <div className="snapshot-history">
        <button className="btn btn-secondary" onClick={() => loadSnapshots(1, '')}>
          Загрузить историю
        </button>
      </div>
    );
  }

  const uniqueNicks = Array.from(new Set(snapshots.map(s => s.nick)));

  return (
    <div className="snapshot-history">
      {isAdmin && (
        <div className="sh-section">
          <h3 className="sh-section-title">Управление кэшем</h3>
          <div className="sh-section-description">
            <p>
              Кэш персонажей хранит последние спаршенные данные в течение 1 часа.
              Очистка кэша заставит приложение загрузить свежие данные с сервера dwar.ru при следующем анализе.
            </p>
          </div>

          <div className="sh-cache-block">
            <div className="sh-cache-instructions">
              Выберите персонажей для очистки кэша или оставьте пустым для очистки всего кэша:
            </div>
            <div className="sh-cache-nick-list">
              {uniqueNicks.map(nick => (
                <label key={nick} className="sh-cache-nick-item">
                  <input
                    type="checkbox"
                    checked={cacheSelectedNicks.has(nick)}
                    onChange={() => handleToggleCacheNick(nick)}
                  />
                  <span>{nick}</span>
                </label>
              ))}
            </div>
            <div className="sh-cache-actions">
              <Button
                variant="secondary"
                size="small"
                onClick={handleClearCache}
                disabled={isClearingCache}
              >
                {isClearingCache ? 'Очистка...' : `Очистить кэш${cacheSelectedNicks.size > 0 ? ` (${cacheSelectedNicks.size})` : ' (весь)'}`}
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="sh-divider" />

      <div className="sh-section">
        <h3 className="sh-section-title">История слепков</h3>
        <div className="sh-section-description">
          <p>
            Слепки — это сохранённые результаты анализа персонажей.
            Они хранятся в базе данных и не зависят от кэша.
          </p>
        </div>

        <div className="sh-header">
          <form className="sh-search" onSubmit={handleSearch}>
            <input
              type="text"
              className="sh-search-input"
              placeholder="Поиск по нику..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button type="submit" className="btn btn-secondary btn-sm">Найти</button>
          </form>
          <div className="sh-actions">
            <label className="sh-select-all-label">
              <input
                type="checkbox"
                checked={selectedIds.size === snapshots.length && snapshots.length > 0}
                onChange={handleSelectAll}
              />
              Выбрать все
            </label>
            <Button variant="ghost" size="small" onClick={handleGroupDeleteClick} disabled={selectedIds.size === 0}>
              Удалить выбранные ({selectedIds.size})
            </Button>
            <Button variant="danger" size="small" onClick={() => setDeleteId(-1)}>
              Удалить все
            </Button>
          </div>
        </div>

        {isLoading && <LoadingSpinner />}

        {!isLoading && snapshots.length === 0 && (
          <p className="sh-empty">Слепки не найдены</p>
        )}

        {!isLoading && snapshots.length > 0 && (
          <>
            <div className="sh-list">
              {snapshots.map((s) => (
                <SnapshotCard
                  key={s.id}
                  snapshot={s}
                  onLoad={handleLoad}
                  onDelete={handleDeleteClick}
                  selected={selectedIds.has(s.id)}
                  onSelect={handleToggleSelect}
                />
              ))}
            </div>
            {totalPages > 1 && (
              <div className="sh-pagination">
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={page === 1}
                  onClick={() => { setPage(p => p - 1); loadSnapshots(page - 1, search); }}
                >
                  Назад
                </button>
                <span className="sh-page-info">{page} / {totalPages}</span>
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={page === totalPages}
                  onClick={() => { setPage(p => p + 1); loadSnapshots(page + 1, search); }}
                >
                  Вперёд
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <Modal
        isOpen={deleteId !== null}
        onClose={handleDeleteCancel}
        title={deleteId === -1 ? 'Удаление всех слепков' : 'Удаление слепка'}
      >
        <div className="modal-delete-confirm">
          <p>
            {deleteId === -1
              ? 'Вы уверены, что хотите удалить ВСЕ слепки? Это действие нельзя отменить.'
              : 'Вы уверены, что хотите удалить этот слепок?'}
          </p>
          <div className="modal-delete-actions">
            <Button variant="ghost" onClick={handleDeleteCancel}>Отмена</Button>
            <Button variant="danger" onClick={handleDeleteConfirm}>Удалить</Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showGroupDelete}
        onClose={handleGroupDeleteCancel}
        title="Удаление выбранных слепков"
      >
        <div className="modal-delete-confirm">
          <p>Вы уверены, что хотите удалить {selectedIds.size} выбранных слепков?</p>
          <div className="modal-delete-actions">
            <Button variant="ghost" onClick={handleGroupDeleteCancel}>Отмена</Button>
            <Button variant="danger" onClick={handleGroupDeleteConfirm}>Удалить</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
