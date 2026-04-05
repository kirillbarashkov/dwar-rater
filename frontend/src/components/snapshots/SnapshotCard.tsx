import type { Snapshot } from '../../types/snapshot';
import './SnapshotCard.css';

interface SnapshotCardProps {
  snapshot: Snapshot;
  onLoad: (id: number) => void;
  onDelete: (id: number) => void;
}

export function SnapshotCard({ snapshot, onLoad, onDelete }: SnapshotCardProps) {
  const date = new Date(snapshot.analyzed_at);
  const formatted = date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="snapshot-card">
      <div className="sc-info">
        <h4 className="sc-name">{snapshot.name}</h4>
        <div className="sc-meta">
          <span>{snapshot.race}</span>
          {snapshot.clan && <span className="sc-clan">{snapshot.clan}</span>}
          <span className="sc-date">{formatted}</span>
        </div>
        {snapshot.snapshot_name && (
          <span className="sc-snapshot-name">{snapshot.snapshot_name}</span>
        )}
      </div>
      <div className="sc-actions">
        <button className="btn btn-secondary btn-sm" onClick={() => onLoad(snapshot.id)}>
          Загрузить
        </button>
        <button className="btn btn-ghost btn-sm btn-danger-text" onClick={() => onDelete(snapshot.id)}>
          Удалить
        </button>
      </div>
    </div>
  );
}
