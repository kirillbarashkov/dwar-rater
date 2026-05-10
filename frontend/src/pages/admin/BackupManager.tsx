import { useState, useEffect, useCallback } from 'react';
import apiClient from '../../api/client';
import './BackupManager.css';

interface Backup {
  filename: string;
  size: number;
  size_human: string;
  created_at: string;
}

export function BackupManager() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [totalSize, setTotalSize] = useState('');
  const [schedule, setSchedule] = useState('');
  const [retention, setRetention] = useState('');
  const [error, setError] = useState('');

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
      fetchBackups();
    } catch (e: unknown) {
      setError((e as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Ошибка создания бэкапа');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`Удалить бэкап ${filename}?`)) return;
    try {
      await apiClient.delete(`/api/admin/backups/${filename}`);
      fetchBackups();
    } catch {
      alert('Ошибка удаления');
    }
  };

  const handleDownload = (filename: string) => {
    const link = document.createElement('a');
    link.href = `/api/admin/backups/${filename}/download`;
    link.download = filename;
    link.click();
  };

  const handleRestore = async (filename: string) => {
    if (!confirm(`Восстановить БД из бэкапа ${filename}? Все текущие данные будут заменены.`)) return;
    setRestoring(filename);
    setError('');
    try {
      await apiClient.post(`/api/admin/backups/${filename}/restore`);
      alert('Бэкап успешно восстановлен');
    } catch (e: unknown) {
      setError((e as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Ошибка восстановления');
    } finally {
      setRestoring(null);
    }
  };

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
                  onClick={() => handleRestore(b.filename)}
                  disabled={restoring === b.filename}
                >
                  {restoring === b.filename ? 'Восстановление...' : 'Восстановить'}
                </button>
                <button className="btn btn-danger btn-sm" onClick={() => handleDelete(b.filename)}>
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
    </div>
  );
}
