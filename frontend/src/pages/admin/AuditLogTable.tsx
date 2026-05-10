import { useState, useEffect, useCallback } from 'react';
import apiClient from '../../api/client';

interface AuditEntry {
  id: number;
  user_id: number | null;
  username: string;
  action: string;
  target_type: string | null;
  target_id: number | null;
  old_value: string | null;
  new_value: string | null;
  ip_address: string | null;
  created_at: string;
}

export function AuditLogTable() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filterAction, setFilterAction] = useState('');
  const [filterTarget, setFilterTarget] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '50' });
      if (filterAction) params.set('action', filterAction);
      if (filterTarget) params.set('target_type', filterTarget);

      const res = await apiClient.get(`/api/admin/audit?${params}`);
      setEntries(res.data.entries);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [page, filterAction, filterTarget]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="audit-log-table">
      <div className="audit-log-header">
        <h2>Audit Log ({total})</h2>
        <div className="audit-filters">
          <select value={filterAction} onChange={(e) => { setFilterAction(e.target.value); setPage(1); }}>
            <option value="">Все действия</option>
            <option value="login">login</option>
            <option value="logout">logout</option>
            <option value="user_create">user_create</option>
            <option value="user_update">user_update</option>
            <option value="user_deactivate">user_deactivate</option>
            <option value="user_sync_create">user_sync_create</option>
            <option value="role_permissions_update">role_permissions_update</option>
            <option value="user_permissions_update">user_permissions_update</option>
            <option value="password_change">password_change</option>
            <option value="2fa_setup">2fa_setup</option>
            <option value="2fa_verified">2fa_verified</option>
            <option value="2fa_disabled">2fa_disabled</option>
          </select>
          <select value={filterTarget} onChange={(e) => { setFilterTarget(e.target.value); setPage(1); }}>
            <option value="">Все цели</option>
            <option value="user">user</option>
            <option value="role">role</option>
            <option value="permission">permission</option>
            <option value="session">session</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="admin-loading">Загрузка...</div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Время</th>
                <th>Пользователь</th>
                <th>Действие</th>
                <th>Цель</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td>{new Date(e.created_at).toLocaleString('ru')}</td>
                  <td>{e.username}</td>
                  <td><code>{e.action}</code></td>
                  <td>{e.target_type}{e.target_id ? ` #${e.target_id}` : ''}</td>
                  <td>{e.ip_address || '—'}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={5} className="empty-row">Нет записей</td></tr>
              )}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="pagination">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)}>← Назад</button>
              <span>Страница {page} из {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Вперёд →</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
