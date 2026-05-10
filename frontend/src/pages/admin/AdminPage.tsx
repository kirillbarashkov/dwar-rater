import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { UserTable } from './UserTable';
import { PermissionMatrix } from './PermissionMatrix';
import { AuditLogTable } from './AuditLogTable';
import { FeatureMatrix } from './FeatureMatrix';
import './AdminPage.css';

const TABS = [
  { key: 'users', label: 'Пользователи' },
  { key: 'permissions', label: 'Роли и права' },
  { key: 'audit', label: 'Audit Log' },
  { key: 'features', label: 'Матрица фич' },
];

export function AdminPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('users');

  if (user?.role !== 'admin') {
    return <div className="admin-access-denied">Доступ запрещён. Только для администраторов.</div>;
  }

  return (
    <div className="admin-page">
      <div className="admin-header">
        <button className="btn btn-ghost admin-back-btn" onClick={() => navigate('/')}>
          ← Назад
        </button>
        <h1 className="admin-title">Администрирование</h1>
      </div>
      <div className="admin-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`admin-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="admin-content">
        {activeTab === 'users' && <UserTable />}
        {activeTab === 'permissions' && <PermissionMatrix />}
        {activeTab === 'audit' && <AuditLogTable />}
        {activeTab === 'features' && <FeatureMatrix />}
      </div>
    </div>
  );
}
