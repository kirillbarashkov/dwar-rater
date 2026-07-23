import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../../components/layout/Header';
import { Sidebar } from '../../components/layout/Sidebar';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { Button } from '../../components/ui/Button';
import { ClanChat } from '../../components/chat/ClanChat';
import { CharacterInfoTab } from '../../components/character/CharacterInfoTab';
import { CharacterCombatTab } from '../../components/character/CharacterCombatTab';
import { CharacterClanTab } from '../../components/character/CharacterClanTab';
import { useAuth } from '../../hooks/useAuth';
import { getMyCharacter, refreshMyCharacter } from '../../api/character';
import { showToast } from '../../components/ui/Toast';
import type { AnalysisResult } from '../../types/character';
import './CharacterPageWrapper.css';

const CACHE_STALE_MS = 60 * 60 * 1000;

export function CharacterPageWrapper() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [chatOpen, setChatOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('info');
  const [activeGroup, setActiveGroup] = useState('character');

  const [character, setCharacter] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);
  const [isCacheStale, setIsCacheStale] = useState(false);

  const hasBinding = !!user?.character_url;

  useEffect(() => {
    if (!hasBinding) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getMyCharacter()
      .then((data) => {
        setCharacter(data);
        setFetchedAt(new Date());
      })
      .catch((err) => {
        const status = err?.response?.status;
        if (status === 404) {
          setError('character_url_not_set');
        } else {
          setError(err?.response?.data?.error ?? 'Ошибка загрузки персонажа');
        }
      })
      .finally(() => setLoading(false));
  }, [hasBinding]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    refreshMyCharacter()
      .then((data) => {
        setCharacter(data);
        setFetchedAt(new Date());
        showToast('Данные персонажа обновлены', 'success');
      })
      .catch((err) => {
        showToast(err?.response?.data?.error ?? 'Ошибка обновления', 'error');
      })
      .finally(() => setRefreshing(false));
  }, []);

  useEffect(() => {
    if (!fetchedAt) {
      setIsCacheStale(false);
      return;
    }
    const checkStale = () => {
      setIsCacheStale(Date.now() - fetchedAt.getTime() > CACHE_STALE_MS);
    };
    checkStale();
    const interval = setInterval(checkStale, 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchedAt]);

  const handleToggleChat = useCallback(() => setChatOpen((prev) => !prev), []);

  const handleTabChange = (groupKey: string, tabKey: string) => {
    setActiveGroup(groupKey);
    setActiveTab(tabKey);
  };

  const renderContent = () => {
    if (activeGroup === 'character') {
      switch (activeTab) {
        case 'info': return <CharacterInfoTab character={character} fetchedAt={fetchedAt} onRefresh={handleRefresh} refreshing={refreshing} />;
        case 'combat': return <CharacterCombatTab character={character} />;
        case 'clan': return <CharacterClanTab />;
      }
    }
    return null;
  };

  if (!hasBinding && !loading) {
    return (
      <div className="app">
        <Header />
        <div className="app-layout">
          <Sidebar
            activeTab={activeTab}
            onTabChange={handleTabChange}
            chatOpen={chatOpen}
            onToggleChat={handleToggleChat}
          />
          <main className="main-content">
            <div className="character-empty-state">
              <div className="character-empty-icon">🧙</div>
              <h2 className="character-empty-title">Персонаж не привязан</h2>
              <p className="character-empty-desc">
                Чтобы увидеть информацию о своём персонаже, укажите ник или ссылку на страницу
                персонажа в dwar.ru в настройках профиля.
              </p>
              <Button variant="primary" onClick={() => navigate('/profile')}>
                Перейти в профиль
              </Button>
            </div>
          </main>
        </div>
        {chatOpen && <ClanChat onClose={() => setChatOpen(false)} />}
      </div>
    );
  }

  return (
    <div className="app">
      <Header />
      <div className="app-layout">
        <Sidebar
          activeTab={activeTab}
          onTabChange={handleTabChange}
          chatOpen={chatOpen}
          onToggleChat={handleToggleChat}
        />
        <main className="main-content">
          <div className="character-page-content">
            {loading && <LoadingSpinner />}

            {!loading && error && error !== 'character_url_not_set' && (
              <div className="character-error-banner">
                <p>{error}</p>
                <Button variant="ghost" onClick={handleRefresh} disabled={refreshing}>
                  {refreshing ? 'Обновление...' : 'Повторить'}
                </Button>
              </div>
            )}

            {!loading && !error && character && (
              <>
                {isCacheStale && (
                  <div className="character-cache-warning">
                    Данные загружены {fetchedAt?.toLocaleString('ru-RU')}. Возможно, они устарели.
                  </div>
                )}
                {renderContent()}
              </>
            )}
          </div>
        </main>
      </div>
      {chatOpen && <ClanChat onClose={() => setChatOpen(false)} />}
    </div>
  );
}
