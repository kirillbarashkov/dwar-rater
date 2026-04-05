import { useState } from 'react';
import { useAuth } from './hooks/useAuth';
import { Header } from './components/layout/Header';
import { Button } from './components/ui/Button';
import { Input } from './components/ui/Input';
import { LoadingSpinner } from './components/ui/LoadingSpinner';
import './styles/globals.css';

function LoginForm() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await login(username, password);
    } catch {
      setError('Неверный логин или пароль');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-section">
      <div className="login-card">
        <h2>Вход</h2>
        <form onSubmit={handleSubmit}>
          <Input
            label="Логин"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <Input
            label="Пароль"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
          {error && <p className="login-error">{error}</p>}
          <Button type="submit" variant="primary" disabled={isLoading}>
            {isLoading ? 'Вход...' : 'Войти'}
          </Button>
        </form>
      </div>
    </div>
  );
}

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    return <LoginForm />;
  }

  return (
    <div className="app">
      <Header />
      <main className="main-content">
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
          Добро пожаловать! Функционал анализа будет добавлен в следующих задачах.
        </p>
      </main>
    </div>
  );
}

export default function App() {
  return <AppContent />;
}
