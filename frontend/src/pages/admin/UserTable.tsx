import { useState, useEffect, useCallback } from 'react';
import apiClient from '../../api/client';
import { showToast } from '../../components/ui/Toast';
import { ConfirmModal } from '../../components/ui/ConfirmModal';
import { UserPermissionsModal } from './UserPermissionsModal';

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
  const [deactivateTarget, setDeactivateTarget] = useState<User | null>(null);
  const [permsTarget, setPermsTarget] = useState<User | null>(null);

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
      showToast('Пользователь создан', 'success');
      fetchUsers();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Ошибка';
      showToast(msg, 'error');
    }
  };

  const handleRoleChange = async (userId: number, role: string) => {
    try {
      await apiClient.put(`/api/admin/users/${userId}`, { role });
      showToast('Роль обновлена', 'success');
      fetchUsers();
    } catch {
      showToast('Ошибка смены роли', 'error');
    }
  };

  const handleDeactivate = async () => {
    if (!deactivateTarget) return;
    try {
      await apiClient.delete(`/api/admin/users/${deactivateTarget.id}`);
      showToast('Пользователь деактивирован', 'success');
      setDeactivateTarget(null);
      fetchUsers();
    } catch {
      showToast('Ошибка деактивации', 'error');
      setDeactivateTarget(null);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await apiClient.post('/api/admin/users/sync');
      setSyncResult(res.data);
      showToast('Синхронизация завершена', 'success');
      fetchUsers();
    } catch {
      showToast('Ошибка синхронизации', 'error');
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
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => setPermsTarget(u)}>
                    Права
                  </button>
                  {u.is_active && (
                    <button className="btn btn-danger btn-sm" onClick={() => setDeactivateTarget(u)}>
                      Деактивировать
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ConfirmModal
        isOpen={deactivateTarget !== null}
        title="Деактивация пользователя"
        message={`Деактивировать пользователя "${deactivateTarget?.username}"? Все активные сессии будут завершены.`}
        confirmLabel="Деактивировать"
        danger
        onConfirm={handleDeactivate}
        onClose={() => setDeactivateTarget(null)}
      />

      {permsTarget && (
        <UserPermissionsModal
          userId={permsTarget.id}
          username={permsTarget.username}
          isOpen={true}
          onClose={() => setPermsTarget(null)}
        />
      )}
    </div>
  );
}