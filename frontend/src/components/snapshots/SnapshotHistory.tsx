import { useState } from 'react';
import type { Snapshot } from '../../types/snapshot';
import { getSnapshots } from '../../api/snapshots';
import { SnapshotCard } from './SnapshotCard';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import './SnapshotHistory.css';

interface SnapshotHistoryProps {
  onLoad: (snapshot: Snapshot & Record<string, unknown>) => void;
}

export function SnapshotHistory({ onLoad }: SnapshotHistoryProps) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [totalPages, setTotalPages] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasFetched, setHasFetched] = useState(false);

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

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить этот слепок?')) return;
    try {
      const { deleteSnapshot } = await import('../../api/snapshots');
      await deleteSnapshot(id);
      loadSnapshots(page, search);
    } catch {
      // ignore
    }
  };

  if (!hasFetched) {
    return (
      <div className="snapshot-history">
        <h3 className="sh-title">История слепков</h3>
        <button className="btn btn-secondary" onClick={() => loadSnapshots(1, '')}>
          Загрузить историю
        </button>
      </div>
    );
  }

  return (
    <div className="snapshot-history">
      <h3 className="sh-title">История слепков</h3>
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
                onDelete={handleDelete}
              />
            ))}
          </div>
          {totalPages > 1 && (
            <div className="sh-pagination">
              <button
                className="btn btn-ghost btn-sm"
                disabled={page <= 1}
                onClick={() => { setPage(page - 1); loadSnapshots(page - 1, search); }}
              >
                Назад
              </button>
              <span className="sh-page-info">{page} / {totalPages}</span>
              <button
                className="btn btn-ghost btn-sm"
                disabled={page >= totalPages}
                onClick={() => { setPage(page + 1); loadSnapshots(page + 1, search); }}
              >
                Вперёд
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
