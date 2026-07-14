import { useState, useEffect, useCallback } from 'react';
import apiClient from '../../api/client';
import { showToast } from '../../components/ui/Toast';
import { ConfirmModal } from '../../components/ui/ConfirmModal';
import './BackupManager.css';

interface Backup {
  filename: string;
  size: number;
  size_human: string;
  created_at: string;
}

type ConfirmState =
  | { type: 'delete'; filename: string }
  | { type: 'restore'; filename: string }
  | null;

export function BackupManager() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [totalSize, setTotalSize] = useState('');
  const [schedule, setSchedule] = useState('');
  const [retention, setRetention] = useState('');
  const [error, setError] = useState('');
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);

  const fetchBackups = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/admin/backups');
      setBackups(res.data.backups);
      setTotalSize(res.data.total_size);
      setSchedule(res.data.schedule);
      setRetention(res.data.retention);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchBackups(); }, [fetchBackups]);

  const handleCreate = async () => {
    setCreating(true);
    setError('');
    try {
      await apiClient.post('/api/admin/backups');
      showToast('Бэкап создан', 'success');
      fetchBackups();
    } catch (e: unknown) {
      setError((e as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Ошибка создания бэкапа');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (filename: string) => {
    try {
      await apiClient.delete(`/api/admin/backups/${filename}`);
      showToast('Бэкап удалён', 'success');
      setConfirmState(null);
      fetchBackups();
    } catch {
      showToast('Ошибка удаления', 'error');
      setConfirmState(null);
    }
  };

  const handleDownload = (filename: string) => {
    const link = document.createElement('a');
    link.href = `/api/admin/backups/${filename}/download`;
    link.download = filename;
    link.click();
  };

  const handleRestore = async (filename: string) => {
    setRestoring(filename);
    setError('');
    try {
      await apiClient.post(`/api/admin/backups/${filename}/restore`);
      showToast('Бэкап успешно восстановлен', 'success');
    } catch (e: unknown) {
      setError((e as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Ошибка восстановления');
    } finally {
      setRestoring(null);
      setConfirmState(null);
    }
  };

  const handleConfirm = () => {
    if (!confirmState) return;
    if (confirmState.type === 'delete') {
      handleDelete(confirmState.filename);
    } else if (confirmState.type === 'restore') {
      handleRestore(confirmState.filename);
    }
  };

  const confirmTitle = confirmState?.type === 'restore'
    ? 'Восстановление БД'
    : 'Удаление бэкапа';
  const confirmMessage = confirmState?.type === 'restore'
    ? `Восстановить БД из бэкапа "${confirmState.filename}"? Все текущие данные будут заменены.`
    : `Удалить бэкап "${confirmState?.filename}"?`;

  if (loading) return <div className="admin-loading">Загрузка...</div>;

  return (
    <div className="backup-manager">
      <div className="backup-header">
        <h2>Бэкапы базы данных</h2>
        <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
          {creating ? 'Создание...' : 'Создать бэкап'}
        </button>
      </div>

      <div className="backup-info">
        <div className="backup-info-item">
          <span className="backup-info-label">Расписание:</span>
          <span>{schedule}</span>
        </div>
        <div className="backup-info-item">
          <span className="backup-info-label">Хранение:</span>
          <span>{retention}</span>
        </div>
        <div className="backup-info-item">
          <span className="backup-info-label">Всего бэкапов:</span>
          <span>{backups.length}</span>
        </div>
        <div className="backup-info-item">
          <span className="backup-info-label">Общий размер:</span>
          <span>{totalSize}</span>
        </div>
      </div>

      {error && <div className="backup-error">{error}</div>}

      <table className="data-table">
        <thead>
          <tr>
            <th>Файл</th>
            <th>Размер</th>
            <th>Дата создания</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {backups.map((b) => (
            <tr key={b.filename}>
              <td className="backup-filename">{b.filename}</td>
              <td>{b.size_human}</td>
              <td>{new Date(b.created_at).toLocaleString('ru')}</td>
              <td className="backup-actions">
                <button className="btn btn-secondary btn-sm" onClick={() => handleDownload(b.filename)}>
                  Скачать
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => setConfirmState({ type: 'restore', filename: b.filename })}
                  disabled={restoring === b.filename}
                >
                  {restoring === b.filename ? 'Восстановление...' : 'Восстановить'}
                </button>
                <button className="btn btn-danger btn-sm" onClick={() => setConfirmState({ type: 'delete', filename: b.filename })}>
                  Удалить
                </button>
              </td>
            </tr>
          ))}
          {backups.length === 0 && (
            <tr>
              <td colSpan={4} className="empty-row">Нет бэкапов. Создайте первый вручную.</td>
            </tr>
          )}
        </tbody>
      </table>

      <ConfirmModal
        isOpen={confirmState !== null}
        title={confirmTitle}
        message={confirmMessage}
        confirmLabel={confirmState?.type === 'restore' ? 'Восстановить' : 'Удалить'}
        danger
        onConfirm={handleConfirm}
        onClose={() => setConfirmState(null)}
      />
    </div>
  );
}