import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { useCharacterAnalysis } from './hooks/useCharacterAnalysis';
import { Header } from './components/layout/Header';
import { SearchBar } from './components/layout/SearchBar';
import { Button } from './components/ui/Button';
import { Input } from './components/ui/Input';
import { ProtectedRoute } from './components/ui/ProtectedRoute';
import { LoadingSpinner } from './components/ui/LoadingSpinner';
import type { AnalysisResult } from './types/character';
import './styles/globals.css';

function LoginPage() {
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

function AnalysisResultDisplay({ result }: { result: AnalysisResult }) {
  return (
    <div className="analysis-result">
      <div className="result-header">
        <h2>{result.name}</h2>
        <div className="result-meta">
          <span>{result.race}</span>
          <span>{result.rank}</span>
          {result.clan && <span>{result.clan}</span>}
        </div>
      </div>
      <div className="result-stats">
        <div className="stat-card">
          <h3>Бои</h3>
          <p>Побед: {result.wins}</p>
          <p>Поражений: {result.losses}</p>
          <p>Винрейт: {result.winrate}%</p>
        </div>
        <div className="stat-card">
          <h3>Убийства</h3>
          <p>{result.kills}</p>
        </div>
      </div>
    </div>
  );
}

function HomePage() {
  const { result, isLoading, error, analyze, clearResult } = useCharacterAnalysis();

  return (
    <div className="app">
      <Header />
      <main className="main-content">
        <SearchBar onAnalyze={analyze} isLoading={isLoading} />

        {isLoading && <LoadingSpinner />}

        {error && (
          <div className="error-banner">
            <p>{error}</p>
            <Button variant="ghost" onClick={clearResult}>Закрыть</Button>
          </div>
        )}

        {result && !isLoading && (
          <AnalysisResultDisplay result={result} />
        )}

        {!result && !isLoading && !error && (
          <p className="placeholder-text">
            Введите ссылку на персонажа dwar.ru для анализа
          </p>
        )}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <HomePage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
