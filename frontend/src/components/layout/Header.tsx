import { useAuth } from '../../hooks/useAuth';
import './Header.css';

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="app-header">
      <h1>Dwar Rater</h1>
      <p className="subtitle">Анализ персонажей Legend: Legacy of the Dragons</p>
      <div className="header-actions">
        {user && (
          <div className="user-info">
            <span className="username">{user.username}</span>
            <span className={`role-badge role-${user.role}`}>{user.role}</span>
            <button className="btn btn-ghost btn-sm" onClick={logout}>
              Выйти
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
