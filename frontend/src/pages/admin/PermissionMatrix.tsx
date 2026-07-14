import { useState, useEffect, useCallback, useMemo } from 'react';
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

type Level = 'full' | 'read' | 'none';
type ChangeMap = Record<string, Level>;

const LEVEL_LABELS: Record<Level, string> = {
  full: 'Полный',
  read: 'Чтение',
  none: 'Нет',
};

export function PermissionMatrix() {
  const [permissions, setPermissions] = useState<PermissionEntry[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingRole, setSavingRole] = useState<string | null>(null);
  const [changes, setChanges] = useState<ChangeMap>({});
  const [search, setSearch] = useState('');
  const [showDiff, setShowDiff] = useState(false);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/admin/permissions');
      setPermissions(res.data.permissions);
      setRoles(res.data.roles);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const changeKey = (permId: number, roleName: string) => `${permId}:${roleName}`;

  const handleLevelChange = (permId: number, roleName: string, level: Level) => {
    setChanges((prev) => ({ ...prev, [changeKey(permId, roleName)]: level }));
  };

  const changesForRole = (roleName: string): Record<number, string> => {
    const result: Record<number, string> = {};
    for (const [key, level] of Object.entries(changes)) {
      const [permIdStr, role] = key.split(':');
      if (role === roleName) result[Number(permIdStr)] = level;
    }
    return result;
  };

  const changedRoles = useMemo(() => {
    const roleSet = new Set<string>();
    for (const key of Object.keys(changes)) {
      const [, role] = key.split(':');
      roleSet.add(role);
    }
    return Array.from(roleSet);
  }, [changes]);

  const handleSaveRole = async (roleName: string) => {
    const role = roles.find((r) => r.name === roleName);
    if (!role) return;

    const roleChanges = changesForRole(roleName);
    if (Object.keys(roleChanges).length === 0) return;

    setSavingRole(roleName);
    setError('');
    try {
      await apiClient.put(`/api/admin/permissions/role/${role.id}`, { permissions: roleChanges });
      setChanges((prev) => {
        const next = { ...prev };
        for (const key of Object.keys(next)) {
          if (key.endsWith(`:${roleName}`)) delete next[key];
        }
        return next;
      });
      await fetchData();
    } catch {
      setError('Ошибка сохранения');
    } finally {
      setSavingRole(null);
    }
  };

  const handleSaveAll = async () => {
    for (const roleName of changedRoles) {
      await handleSaveRole(roleName);
    }
  };

  const handleReset = () => {
    setChanges({});
    setShowDiff(false);
  };

  const filteredPermissions = useMemo(() => {
    if (!search) return permissions;
    const q = search.toLowerCase();
    return permissions.filter((p) =>
      p.feature.toLowerCase().includes(q) ||
      p.action.toLowerCase().includes(q) ||
      p.label.toLowerCase().includes(q)
    );
  }, [permissions, search]);

  const grouped = useMemo(() => {
    return filteredPermissions.reduce<Record<string, PermissionEntry[]>>((acc, p) => {
      if (!acc[p.feature]) acc[p.feature] = [];
      acc[p.feature].push(p);
      return acc;
    }, {});
  }, [filteredPermissions]);

  if (loading) return <div className="admin-loading">Загрузка...</div>;

  return (
    <div className="permission-matrix">
      <div className="permission-matrix-header">
        <h2>Роли и права</h2>
        <div className="matrix-actions">
          <input
            type="search"
            placeholder="Поиск по фичам и правам..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="matrix-search"
          />
          {Object.keys(changes).length > 0 && (
            <>
              <button className="btn btn-ghost" onClick={() => setShowDiff(!showDiff)}>
                {showDiff ? 'Скрыть diff' : `Diff (${Object.keys(changes).length})`}
              </button>
              <button className="btn btn-ghost" onClick={handleReset}>
                Сбросить
              </button>
            </>
          )}
        </div>
      </div>

      {error && <div className="admin-warning">{error}</div>}

      {showDiff && Object.keys(changes).length > 0 && (
        <div className="diff-preview">
          <h3>Предпросмотр изменений</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Фича:Действие</th>
                <th>Роль</th>
                <th>Было</th>
                <th>Станет</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(changes).map(([key, newLevel]) => {
                const [permIdStr, roleName] = key.split(':');
                const permId = Number(permIdStr);
                const perm = permissions.find((p) => p.id === permId);
                if (!perm) return null;
                const oldLevel = (perm.roles[roleName] ?? 'none') as Level;
                return (
                  <tr key={key}>
                    <td><code>{perm.feature}:{perm.action}</code></td>
                    <td>{roleName}</td>
                    <td><span className={`level-badge level-${oldLevel}`}>{LEVEL_LABELS[oldLevel]}</span></td>
                    <td><span className={`level-badge level-${newLevel}`}>{LEVEL_LABELS[newLevel]}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {Object.entries(grouped).map(([feature, perms]) => (
        <div key={feature} className="permission-group">
          <h3 className="permission-group-title">{feature}</h3>
          <table className="data-table matrix-table">
            <thead>
              <tr>
                <th className="perm-action-col">Действие</th>
                {roles.map((r) => (
                  <th key={r.name} className={`role-col ${r.is_system ? 'system-role' : ''}`}>
                    {r.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {perms.map((p) => (
                <tr key={p.id}>
                  <td className="perm-action-col">
                    <strong>{p.action}</strong>
                    <br />
                    <span className="perm-label">{p.label}</span>
                  </td>
                  {roles.map((r) => {
                    const currentLevel = (p.roles[r.name] ?? 'none') as Level;
                    const changedLevel = changes[changeKey(p.id, r.name)];
                    const displayLevel = changedLevel ?? currentLevel;
                    const isChanged = !!changedLevel && changedLevel !== currentLevel;
                    const isDisabled = r.is_system && r.name === 'admin';

                    return (
                      <td key={r.name}>
                        <select
                          value={displayLevel}
                          onChange={(e) => handleLevelChange(p.id, r.name, e.target.value as Level)}
                          disabled={isDisabled}
                          className={`level-select level-${displayLevel} ${isChanged ? 'level-changed' : ''}`}
                        >
                          <option value="full">full</option>
                          <option value="read">read</option>
                          <option value="none">none</option>
                        </select>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {changedRoles.length > 0 && (
        <div className="matrix-save-bar">
          <span>Изменений: {Object.keys(changes).length} для {changedRoles.length} ролей</span>
          {changedRoles.map((roleName) => (
            <button
              key={roleName}
              className="btn btn-secondary btn-sm"
              onClick={() => handleSaveRole(roleName)}
              disabled={savingRole === roleName}
            >
              {savingRole === roleName ? 'Сохранение...' : `Сохранить (${roleName})`}
            </button>
          ))}
          <button
            className="btn btn-primary"
            onClick={handleSaveAll}
            disabled={savingRole !== null}
          >
            {savingRole ? 'Сохранение...' : 'Сохранить всё'}
          </button>
        </div>
      )}
    </div>
  );
}