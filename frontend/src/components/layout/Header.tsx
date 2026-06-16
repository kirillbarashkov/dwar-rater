import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePermission } from '../../hooks/useAuth';
import { DeployModal } from './DeployModal';
import './Header.css';

function getInitialTheme(): string {
  const stored = localStorage.getItem('theme');
  if (stored) return stored;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function Header() {
  const { user, logout } = useAuth();
  const [theme, setTheme] = useState(getInitialTheme);
  const [versionInfo, setVersionInfo] = useState<{
    version: string;
    git_hash: string;
    build_date: string;
    branch: string;
  } | null>(null);
  const [showDeployModal, setShowDeployModal] = useState(false);
  const canDeploy = usePermission('admin', 'deploy') === 'full';

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    fetch('/api/version')
      .then(r => r.json())
      .then(setVersionInfo)
      .catch(() => {});
  }, []);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <header className="app-header">
      <div className="header-brand">
        <span className="header-logo">⚔️</span>
        <div className="header-title-group">
          <h1 className="header-title">Dwar Rater</h1>
          <p className="header-subtitle">Анализ персонажей Legend: Legacy of the Dragons</p>
        </div>
      </div>
      <div className="header-actions">
        {versionInfo && (
          <div className="version-info" title={`${versionInfo.build_date} · ${versionInfo.git_hash} · ${versionInfo.branch}`}>
            <span className="version-tag">v{versionInfo.version}</span>
            {canDeploy && (
              <button
                className="deploy-trigger"
                onClick={() => setShowDeployModal(true)}
                title="Deploy to production"
                aria-label="Deploy"
              >
                ⚡
              </button>
            )}
          </div>
        )}
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
        {user && (
          <div className="user-info">
            <span className="user-avatar">👤</span>
            <div className="user-details">
              <span className="username">{user.username}</span>
              <span className={`role-badge role-${user.role}`}>{user.role}</span>
            </div>
            <button className="btn btn-ghost btn-sm logout-btn" onClick={logout} title="Выйти">
              🚪
            </button>
          </div>
        )}
      </div>
      {showDeployModal && (
        <DeployModal
          onClose={() => setShowDeployModal(false)}
          currentVersion={versionInfo?.version || '0.0.0'}
        />
      )}
    </header>
  );
}
