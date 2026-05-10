import { useState, useEffect, useCallback } from 'react';
import apiClient from '../../api/client';

interface PermissionEntry {
  id: number;
  feature: string;
  action: string;
  label: string;
  description: string;
  roles: Record<string, string>;
}

interface Role {
  id: number;
  name: string;
  label: string;
  is_system: boolean;
}

export function PermissionMatrix() {
  const [permissions, setPermissions] = useState<PermissionEntry[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedRole, setSelectedRole] = useState('');
  const [changes, setChanges] = useState<Record<number, string>>({});

  const fetchData = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/admin/permissions');
      setPermissions(res.data.permissions);
      setRoles(res.data.roles);
      if (!selectedRole && res.data.roles.length > 0) {
        setSelectedRole(res.data.roles[0].name);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [selectedRole]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleLevelChange = (permId: number, level: string) => {
    setChanges((prev) => ({ ...prev, [permId]: level }));
  };

  const handleSave = async () => {
    if (!selectedRole) return;
    const role = roles.find((r) => r.name === selectedRole);
    if (!role) return;

    setSaving(true);
    try {
      await apiClient.put(`/api/admin/permissions/role/${role.id}`, { permissions: changes });
      setChanges({});
      fetchData();
    } catch {
      alert('Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const role = roles.find((r) => r.name === selectedRole);

  if (loading) return <div className="admin-loading">Загрузка...</div>;

  const grouped = permissions.reduce<Record<string, PermissionEntry[]>>((acc, p) => {
    if (!acc[p.feature]) acc[p.feature] = [];
    acc[p.feature].push(p);
    return acc;
  }, {});

  return (
    <div className="permission-matrix">
      <div className="permission-matrix-header">
        <h2>Роли и права</h2>
        <div className="role-selector">
          <label>Роль:</label>
          <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)}>
            {roles.map((r) => (
              <option key={r.name} value={r.name}>
                {r.label} ({r.name}){r.is_system ? ' [системная]' : ''}
              </option>
            ))}
          </select>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving || Object.keys(changes).length === 0 || role?.is_system}
          >
            {saving ? 'Сохранение...' : `Сохранить (${Object.keys(changes).length})`}
          </button>
        </div>
      </div>

      {role?.is_system && role.name === 'admin' && (
        <div className="admin-warning">Права администратора нельзя изменить — всегда полный доступ.</div>
      )}

      {Object.entries(grouped).map(([feature, perms]) => (
        <div key={feature} className="permission-group">
          <h3 className="permission-group-title">{feature}</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Действие</th>
                <th>Описание</th>
                <th>Уровень</th>
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
                  <td className="perm-description">{p.description}</td>
                  <td>
                    <select
                      value={changes[p.id] ?? p.roles[selectedRole] ?? 'none'}
                      onChange={(e) => handleLevelChange(p.id, e.target.value)}
                      disabled={role?.is_system}
                      className={`level-select level-${changes[p.id] ?? p.roles[selectedRole] ?? 'none'}`}
                    >
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
  );
}
