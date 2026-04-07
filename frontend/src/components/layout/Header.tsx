import { useAuth } from '../../hooks/useAuth';
import './Header.css';

interface HeaderProps {
  onToggleChat: () => void;
  chatOpen: boolean;
}

export function Header({ onToggleChat, chatOpen }: HeaderProps) {
  const { user, logout } = useAuth();

  return (
    <header className="app-header">
      <h1>Dwar Rater</h1>
      <p className="subtitle">Анализ персонажей Legend: Legacy of the Dragons</p>
      <div className="header-actions">
        {user && (
          <div className="user-info">
            <button
              className={`btn btn-ghost btn-sm chat-toggle ${chatOpen ? 'active' : ''}`}
              onClick={onToggleChat}
              title="Клановый чат"
            >
              💬
            </button>
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
