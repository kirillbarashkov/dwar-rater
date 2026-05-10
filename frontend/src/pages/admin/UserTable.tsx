import { useState, useEffect, useCallback } from 'react';
import apiClient from '../../api/client';

interface User {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
  must_change_password: boolean;
  created_at: string | null;
}

export function UserTable() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user' });
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<{ created: number; updated: number; skipped: number } | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/admin/users');
      setUsers(res.data.users);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleCreate = async () => {
    if (!newUser.username || newUser.password.length < 8) return;
    try {
      await apiClient.post('/api/admin/users', newUser);
      setShowCreate(false);
      setNewUser({ username: '', password: '', role: 'user' });
      fetchUsers();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Ошибка';
      alert(msg);
    }
  };

  const handleRoleChange = async (userId: number, role: string) => {
    try {
      await apiClient.put(`/api/admin/users/${userId}`, { role });
      fetchUsers();
    } catch {
      alert('Ошибка смены роли');
    }
  };

  const handleDeactivate = async (userId: number) => {
    if (!confirm('Деактивировать пользователя?')) return;
    try {
      await apiClient.delete(`/api/admin/users/${userId}`);
      fetchUsers();
    } catch {
      alert('Ошибка деактивации');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await apiClient.post('/api/admin/users/sync');
      setSyncResult(res.data);
      fetchUsers();
    } catch {
      alert('Ошибка синхронизации');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) return <div className="admin-loading">Загрузка...</div>;

  return (
    <div className="user-table">
      <div className="user-table-header">
        <h2>Пользователи ({users.length})</h2>
        <div className="user-table-actions">
          <button className="btn btn-secondary" onClick={handleSync} disabled={syncing}>
            {syncing ? 'Синхронизация...' : 'Синхронизировать из клана'}
          </button>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            Создать пользователя
          </button>
        </div>
      </div>

      {syncResult && (
        <div className="sync-result">
          Создано: {syncResult.created}, Обновлено: {syncResult.updated}, Пропущено: {syncResult.skipped}
        </div>
      )}

      {showCreate && (
        <div className="create-user-form">
          <h3>Новый пользователь</h3>
          <input
            type="text"
            placeholder="Логин (латиница, 3-25 символов)"
            value={newUser.username}
            onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
          />
          <input
            type="password"
            placeholder="Пароль (мин. 8 символов)"
            value={newUser.password}
            onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
          />
          <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
            <option value="user">user</option>
            <option value="superuser">superuser</option>
            <option value="custom">custom</option>
            <option value="admin">admin</option>
          </select>
          <div className="create-user-actions">
            <button className="btn btn-primary" onClick={handleCreate}>Создать</button>
            <button className="btn btn-ghost" onClick={() => setShowCreate(false)}>Отмена</button>
          </div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Логин</th>
            <th>Роль</th>
            <th>Статус</th>
            <th>Последний вход</th>
            <th>Смена пароля</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className={!u.is_active ? 'inactive' : ''}>
              <td>{u.username}</td>
              <td>
                <select
                  value={u.role}
                  onChange={(e) => handleRoleChange(u.id, e.target.value)}
                  className="role-select"
                >
                  <option value="user">user</option>
                  <option value="superuser">superuser</option>
                  <option value="custom">custom</option>
                  <option value="admin">admin</option>
                </select>
              </td>
              <td>
                <span className={`status-badge ${u.is_active ? 'active' : 'inactive'}`}>
                  {u.is_active ? 'Активен' : 'Деактивирован'}
                </span>
              </td>
              <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString('ru') : '—'}</td>
              <td>{u.must_change_password ? 'Да' : 'Нет'}</td>
              <td>
                {u.is_active && (
                  <button className="btn btn-danger btn-sm" onClick={() => handleDeactivate(u.id)}>
                    Деактивировать
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
