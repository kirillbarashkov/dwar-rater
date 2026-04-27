import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import './Header.css';

function getInitialTheme(): string {
  const stored = localStorage.getItem('theme');
  if (stored) return stored;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function Header() {
  const { user, logout } = useAuth();
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

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
    </header>
  );
}
