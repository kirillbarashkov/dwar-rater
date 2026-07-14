import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePermission } from '../../hooks/useAuth';
import { UserTable } from './UserTable';
import { PermissionMatrix } from './PermissionMatrix';
import { AuditLogTable } from './AuditLogTable';
import { FeatureMatrix } from './FeatureMatrix';
import { BackupManager } from './BackupManager';
import './AdminPage.css';

interface TabDef {
  key: string;
  label: string;
  requiredLevel: 'read' | 'admin';
}

const ALL_TABS: TabDef[] = [
  { key: 'users', label: 'Пользователи', requiredLevel: 'read' },
  { key: 'permissions', label: 'Роли и права', requiredLevel: 'read' },
  { key: 'backups', label: 'Бэкапы БД', requiredLevel: 'read' },
  { key: 'audit', label: 'Audit Log', requiredLevel: 'admin' },
  { key: 'features', label: 'Матрица фич', requiredLevel: 'read' },
];

export function AdminPage() {
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<string>(() => {
    return new URLSearchParams(window.location.search).get('tab') ?? 'users';
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set('tab', activeTab);
    window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
  }, [activeTab]);

  const canReadAdmin = usePermission('admin', 'read') === 'full';
  const canViewAudit = usePermission('admin', 'admin') === 'full';

  const visibleTabs = ALL_TABS.filter((tab) =>
    tab.requiredLevel === 'admin' ? canViewAudit : canReadAdmin
  );

  if (visibleTabs.length === 0) {
    return <div className="admin-access-denied">Доступ запрещён.</div>;
  }

  const currentTab = visibleTabs.find((t) => t.key === activeTab) ?? visibleTabs[0];

  return (
    <div className="admin-page">
      <div className="admin-header">
        <button className="btn btn-ghost admin-back-btn" onClick={() => navigate('/')}>
          ← Назад
        </button>
        <h1 className="admin-title">Администрирование</h1>
      </div>
      <div className="admin-tabs">
        {visibleTabs.map((tab) => (
          <button
            key={tab.key}
            className={`admin-tab ${currentTab.key === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="admin-content">
        {currentTab.key === 'users' && <UserTable />}
        {currentTab.key === 'permissions' && <PermissionMatrix />}
        {currentTab.key === 'backups' && <BackupManager />}
        {currentTab.key === 'audit' && <AuditLogTable />}
        {currentTab.key === 'features' && <FeatureMatrix />}
      </div>
    </div>
  );
}
