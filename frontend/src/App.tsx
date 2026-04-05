import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { useCharacterAnalysis } from './hooks/useCharacterAnalysis';
import { Header } from './components/layout/Header';
import { SearchBar } from './components/layout/SearchBar';
import { Button } from './components/ui/Button';
import { Input } from './components/ui/Input';
import { ProtectedRoute } from './components/ui/ProtectedRoute';
import { LoadingSpinner } from './components/ui/LoadingSpinner';
import { Tabs, TabPanel } from './components/ui/Tabs';
import { CharacterHeader } from './components/analysis/CharacterHeader';
import { StatsTab } from './components/analysis/StatsTab';
import { EquipmentTab } from './components/analysis/EquipmentTab';
import { EffectsTab } from './components/analysis/EffectsTab';
import { RecordsTab } from './components/analysis/RecordsTab';
import { MedalsTab } from './components/analysis/MedalsTab';
import { OtherTab } from './components/analysis/OtherTab';
import './styles/globals.css';

function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
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
      navigate('/', { replace: true });
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

function AnalysisResultDisplay({ result }: { result: ReturnType<typeof useCharacterAnalysis>['result'] }) {
  if (!result) return null;

  const tabs = [
    { key: 'stats', label: 'Характеристики' },
    { key: 'equipment', label: 'Экипировка' },
    { key: 'effects', label: 'Эффекты' },
    { key: 'medals', label: 'Медали' },
    { key: 'records', label: 'Рекорды' },
    { key: 'other', label: 'Прочее' },
  ];

  return (
    <div className="analysis-result">
      <CharacterHeader character={result} />
      <Tabs tabs={tabs} defaultTab="stats">
        <TabPanel tabKey="stats" activeTab="stats">
          <StatsTab character={result} />
        </TabPanel>
        <TabPanel tabKey="equipment" activeTab="equipment">
          <EquipmentTab equipment={result.equipment_by_kind} sets={result.sets} />
        </TabPanel>
        <TabPanel tabKey="effects" activeTab="effects">
          <EffectsTab tempEffects={result.temp_effects} permanentEffects={result.permanent_effects} />
        </TabPanel>
        <TabPanel tabKey="medals" activeTab="medals">
          <MedalsTab medals={result.medals} />
        </TabPanel>
        <TabPanel tabKey="records" activeTab="records">
          <RecordsTab records={result.combat_records} />
        </TabPanel>
        <TabPanel tabKey="other" activeTab="other">
          <OtherTab character={result} />
        </TabPanel>
      </Tabs>
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
