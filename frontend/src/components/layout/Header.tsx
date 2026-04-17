import { useAuth } from '../../hooks/useAuth';
import './Header.css';

export function Header() {
  const { user, logout } = useAuth();

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
