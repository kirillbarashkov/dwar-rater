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
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filterOptions, setFilterOptions] = useState<{ actions: string[]; target_types: string[] } | null>(null);

  const fetchFilters = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/admin/audit/filters');
      setFilterOptions(res.data);
    } catch {
      // ignore — fall back to hardcoded
    }
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '50' });
      if (filterAction) params.set('action', filterAction);
      if (filterTarget) params.set('target_type', filterTarget);
      if (filterDateFrom) params.set('date_from', filterDateFrom);
      if (filterDateTo) params.set('date_to', filterDateTo);

      const res = await apiClient.get(`/api/admin/audit?${params}`);
      setEntries(res.data.entries);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [page, filterAction, filterTarget, filterDateFrom, filterDateTo]);

  useEffect(() => { fetchFilters(); }, [fetchFilters]);
  useEffect(() => { fetchData(); }, [fetchData]);

  const handleExport = async () => {
    try {
      const params = new URLSearchParams({ page: '1', per_page: '10000' });
      if (filterAction) params.set('action', filterAction);
      if (filterTarget) params.set('target_type', filterTarget);
      if (filterDateFrom) params.set('date_from', filterDateFrom);
      if (filterDateTo) params.set('date_to', filterDateTo);

      const res = await apiClient.get(`/api/admin/audit?${params}`);
      const rows = res.data.entries as AuditEntry[];
      const headers = ['Время', 'Пользователь', 'Действие', 'Цель', 'ID цели', 'IP'];
      const lines = [headers.join(';')];
      for (const e of rows) {
        lines.push([
          e.created_at,
          e.username,
          e.action,
          e.target_type ?? '',
          String(e.target_id ?? ''),
          e.ip_address ?? '',
        ].map((v) => `"${v.replace(/"/g, '""')}"`).join(';'));
      }
      const csv = '\uFEFF' + lines.join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `audit_log_${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch {
      // ignore
    }
  };

  const actions = filterOptions?.actions ?? ['login', 'logout', 'user_create', 'user_update', 'user_deactivate', 'user_sync_create', 'role_permissions_update', 'user_permissions_update', 'password_change', '2fa_setup', '2fa_verified', '2fa_disabled'];
  const targetTypes = filterOptions?.target_types ?? ['user', 'role', 'permission', 'session', 'backup'];

  return (
    <div className="audit-log-table">
      <div className="audit-log-header">
        <h2>Audit Log ({total})</h2>
        <button className="btn btn-secondary btn-sm" onClick={handleExport}>
          Экспорт CSV
        </button>
      </div>

      <div className="audit-filters">
        <select value={filterAction} onChange={(e) => { setFilterAction(e.target.value); setPage(1); }}>
          <option value="">Все действия</option>
          {actions.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={filterTarget} onChange={(e) => { setFilterTarget(e.target.value); setPage(1); }}>
          <option value="">Все цели</option>
          {targetTypes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input
          type="date"
          value={filterDateFrom}
          onChange={(e) => { setFilterDateFrom(e.target.value); setPage(1); }}
          title="С даты"
        />
        <input
          type="date"
          value={filterDateTo}
          onChange={(e) => { setFilterDateTo(e.target.value); setPage(1); }}
          title="По дату"
        />
        {(filterAction || filterTarget || filterDateFrom || filterDateTo) && (
          <button className="btn btn-ghost btn-sm" onClick={() => { setFilterAction(''); setFilterTarget(''); setFilterDateFrom(''); setFilterDateTo(''); setPage(1); }}>
            Сбросить
          </button>
        )}
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
                <>
                  <tr
                    key={e.id}
                    onClick={() => setExpandedId(e.id === expandedId ? null : e.id)}
                    className={expandedId === e.id ? 'row-expanded' : 'row-clickable'}
                  >
                    <td>{new Date(e.created_at).toLocaleString('ru')}</td>
                    <td>{e.username}</td>
                    <td><code>{e.action}</code></td>
                    <td>{e.target_type}{e.target_id ? ` #${e.target_id}` : ''}</td>
                    <td>{e.ip_address || '—'}</td>
                  </tr>
                  {expandedId === e.id && (e.old_value || e.new_value) && (
                    <tr key={`${e.id}-detail`} className="detail-row">
                      <td colSpan={5}>
                        <div className="audit-detail">
                          {e.old_value && (
                            <div>
                              <span className="detail-label">Было:</span>
                              <pre>{e.old_value}</pre>
                            </div>
                          )}
                          {e.new_value && (
                            <div>
                              <span className="detail-label">Стало:</span>
                              <pre>{e.new_value}</pre>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
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