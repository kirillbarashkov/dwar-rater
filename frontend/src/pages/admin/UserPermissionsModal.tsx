import { useState, useEffect, useCallback } from 'react';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/Toast';
import apiClient from '../../api/client';

interface UserPermissionEntry {
  id: number;
  feature: string;
  action: string;
  label: string;
  level: string;
}

interface UserInfo {
  id: number;
  username: string;
  role: string;
}

interface UserPermissionsModalProps {
  userId: number;
  username: string;
  isOpen: boolean;
  onClose: () => void;
}

type OverrideLevel = 'inherit' | 'full' | 'read' | 'none';

export function UserPermissionsModal({ userId, username, isOpen, onClose }: UserPermissionsModalProps) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [permissions, setPermissions] = useState<UserPermissionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overrides, setOverrides] = useState<Record<number, OverrideLevel>>({});
  const [search, setSearch] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get(`/api/admin/permissions/user/${userId}`);
      setUser(res.data.user);
      setPermissions(res.data.permissions);
      const existing: Record<number, OverrideLevel> = {};
      for (const p of res.data.permissions as UserPermissionEntry[]) {
        existing[p.id] = (p.level as OverrideLevel) ?? 'inherit';
      }
      setOverrides(existing);
    } catch {
      showToast('Ошибка загрузки прав', 'error');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (isOpen) fetchData();
  }, [isOpen, fetchData]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const permLevelMap: Record<number, string> = {};
      for (const [permId, level] of Object.entries(overrides)) {
        const id = Number(permId);
        const perm = permissions.find((p) => p.id === id);
        if (!perm) continue;
        if (level === 'inherit') {
          continue;
        }
        permLevelMap[id] = level;
      }
      await apiClient.put(`/api/admin/permissions/user/${userId}`, { permissions: permLevelMap });
      showToast('Индивидуальные права сохранены', 'success');
      onClose();
    } catch {
      showToast('Ошибка сохранения', 'error');
    } finally {
      setSaving(false);
    }
  };

  const grouped = permissions.reduce<Record<string, UserPermissionEntry[]>>((acc, p) => {
    if (!acc[p.feature]) acc[p.feature] = [];
    acc[p.feature].push(p);
    return acc;
  }, {});

  const filteredFeatures = Object.entries(grouped).filter(([feature, perms]) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return feature.toLowerCase().includes(q) ||
      perms.some((p) => p.action.toLowerCase().includes(q) || p.label.toLowerCase().includes(q));
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Права: ${username}`} wide>
      <div className="user-perms-modal">
        <div className="user-perms-info">
          <input
            type="search"
            placeholder="Поиск..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="matrix-search"
          />
          <span className="user-perms-role">Роль: <strong>{user?.role}</strong></span>
        </div>

        {loading ? (
          <div className="admin-loading">Загрузка...</div>
        ) : (
          <div className="user-perms-list">
            {filteredFeatures.map(([feature, perms]) => (
              <div key={feature} className="permission-group">
                <h3 className="permission-group-title">{feature}</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Действие</th>
                      <th>Override</th>
                    </tr>
                  </thead>
                  <tbody>
                    {perms.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <strong>{p.action}</strong>
                          <br />
                          <span className="perm-label">{p.label}</span>
                        </td>
                        <td>
                          <select
                            value={overrides[p.id] ?? 'inherit'}
                            onChange={(e) => setOverrides((prev) => ({ ...prev, [p.id]: e.target.value as OverrideLevel }))}
                            className={`level-select level-${overrides[p.id] ?? 'inherit'}`}
                          >
                            <option value="inherit">inherit (роль)</option>
                            <option value="full">full</option>
                            <option value="read">read</option>
                            <option value="none">none</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}

        <div className="confirm-actions" style={{ marginTop: '16px' }}>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving || loading}>
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        </div>
      </div>
    </Modal>
  );
}