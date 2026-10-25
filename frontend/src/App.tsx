import { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useParams, useLocation, useNavigate } from 'react-router-dom';
import { useCharacterAnalysis } from './hooks/useCharacterAnalysis';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { TREASURY_TABS, DEFAULT_CLAN_ID } from './utils/constants';
import { asAnalysisResult } from './utils/analysisShape';
import { toPayload } from './utils/payload';
import { Button } from './components/ui/Button';
import { Input } from './components/ui/Input';
import { Modal } from './components/ui/Modal';
import { ProtectedRoute } from './components/ui/ProtectedRoute';
import { LoadingSpinner } from './components/ui/LoadingSpinner';
import { ToastProvider, showToast } from './components/ui/Toast';
import { StatsTab } from './components/analysis/StatsTab';
import { EquipmentTab } from './components/analysis/EquipmentTab';
import { EffectsTab } from './components/analysis/EffectsTab';
import { RecordsTab } from './components/analysis/RecordsTab';
import { MedalsTab } from './components/analysis/MedalsTab';
import { OtherTab } from './components/analysis/OtherTab';
import { ClosedProfilesTab } from './components/analysis/ClosedProfilesTab';
import { ExportTab } from './pages/analysis/ExportTab';

import { CharacterPanel } from './components/snapshots/CharacterPanel';
import { SnapshotHistory } from './components/snapshots/SnapshotHistory';
import { ClosedProfileBanner } from './components/snapshots/ClosedProfileBanner';
import { ScenarioComparison } from './components/analysis/ScenarioComparison';
import { ImprovementTrackPanel } from './components/analysis/ImprovementTrack';
import { CharacterComparison } from './components/analysis/CharacterComparison';
import { CompareListManager } from './components/clan/CompareListManager';
import { ClanChat } from './components/chat/ClanChat';
import { ClanOverview } from './components/clan/ClanOverview';
import { ClanMembersTable } from './components/clan/ClanMembersTable';
import { TreasuryTab } from './components/clan/TreasuryTab';
import { TreasuryImport } from './components/clan/TreasuryImport';
import { TreasuryAnalytics } from './components/clan/TreasuryAnalytics';
import { TreasuryPairsQueue } from './components/clan/TreasuryPairsQueue';
import { MemberStatusTab } from './components/clan/MemberStatusTab';
import { TreasuryLoansTab } from './components/clan/TreasuryLoansTab';
import { TreasuryExclusionsTab } from './components/clan/TreasuryExclusionsTab';
import { saveSnapshot } from './api/snapshots';
import { addCompareCharacter } from './api/compare';
import type { AnalysisResult } from './types/character';
import type { Snapshot } from './types/snapshot';
import { LoginPage } from './pages/auth/LoginPage';
import { AdminPage } from './pages/admin/AdminPage';
import { ProfilePage } from './pages/profile/ProfilePage';
import { AboutPage } from './pages/about/AboutPage';
import { CharacterPageWrapper } from './pages/character/CharacterPageWrapper';
import './styles/globals.css';

function AnalysisResultDisplay({
  result,
  activeTab,
  onLoadSnapshot,
}: {
  result: ReturnType<typeof useCharacterAnalysis>['result'];
  activeTab: string;
  onLoadSnapshot: (data: Snapshot & Record<string, unknown>) => void;
}) {
  if (activeTab === 'history' || activeTab === 'compare' || activeTab === 'compare-list') {
    return (
      <div className="analysis-result">
        <div className="tab-panels">
          {activeTab === 'history' && <SnapshotHistory onLoad={onLoadSnapshot} />}
          {activeTab === 'compare' && <CharacterComparison />}
          {activeTab === 'compare-list' && <CompareListManager />}
        </div>
      </div>
    );
  }

  if (activeTab === 'closed') {
    return (
      <div className="analysis-result">
        <ClosedProfilesTab />
      </div>
    );
  }

  if (activeTab === 'track') {
    return (
      <div className="analysis-result">
        <div className="tab-panels">
          <ImprovementTrackPanel character={result} />
        </div>
      </div>
    );
  }

  if (!result) return null;

  if (result.profile_closed) {
    return (
      <div className="analysis-result">
        <ClosedProfileBanner character={result} />
      </div>
    );
  }

  return (
    <div className="analysis-result">
      <div className="tab-panels">
        {activeTab === 'stats' && <StatsTab character={result} />}
        {activeTab === 'equipment' && <EquipmentTab equipment={result.equipment_by_kind} sets={result.sets} />}
        {activeTab === 'effects' && <EffectsTab tempEffects={result.temp_effects} permanentEffects={result.permanent_effects} />}
        {activeTab === 'medals' && <MedalsTab medals={result.medals} />}
        {activeTab === 'records' && <RecordsTab records={result.combat_records} />}
        {activeTab === 'other' && <OtherTab character={result} />}
        {activeTab === 'track' && <ImprovementTrackPanel character={result} />}
      </div>
    </div>
  );
}

function HomePage() {
  const { result, isLoading, error, analyze } = useCharacterAnalysis();
  const [currentResult, setCurrentResult] = useState<AnalysisResult | null>(null);
  const [lastAnalyzed, setLastAnalyzed] = useState<Date | null>(null);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [snapshotName, setSnapshotName] = useState('');
  const [chatOpen, setChatOpen] = useState(false);
  // Вкладка может прийти в URL: клик по «Треку улучшений» в боковом меню ведёт сюда
  // переходом. Читаем её при инициализации — ДО эффектов. Это существенно: у эффекта
  // ниже есть ранний выход на отложенный анализ, а после анализа вкладка выставляется
  // в 'stats' («Анализ персонажа»). С уже установленным 'track' код проекта трек
  // сохраняет (prev === 'track' ? 'track' : 'stats'), поэтому инициализация решает.
  const requestedTab = new URLSearchParams(window.location.search).get('tab') ?? '';
  const [activeTab, setActiveTab] = useState(requestedTab || 'stats');
  const [pendingAnalyzeUrl, setPendingAnalyzeUrl] = useState<string | null>(null);
  // Последний запрошенный адрес: нужен, чтобы при ошибке анализа (персонаж закрыт)
  // предложить слепки именно этого персонажа.
  const [lastAnalyzedUrl, setLastAnalyzedUrl] = useState('');
  // Ник из последнего адреса (/user_info.php?nick=…) — по нему ищем слепки.
  const snapshotNickMatch = lastAnalyzedUrl.match(/nick=([^&\s]+)/i);
  const snapshotNick = snapshotNickMatch ? decodeURIComponent(snapshotNickMatch[1]) : '';
  const analyzeTriggered = useRef(false);
  const sessionChecked = useRef(false);

  useEffect(() => {
    if (sessionChecked.current) return;
    sessionChecked.current = true;
    
    const urlFromSession = sessionStorage.getItem('pending_analyze');
    if (urlFromSession) {
      sessionStorage.removeItem('pending_analyze');
      analyzeTriggered.current = true;
      setPendingAnalyzeUrl(urlFromSession);
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const analyzeUrl = params.get('analyze');
    if (analyzeUrl) {
      analyzeTriggered.current = true;
      setPendingAnalyzeUrl(analyzeUrl);
      params.delete('analyze');
      window.history.replaceState({}, '', params.toString() ? `/?${params.toString()}` : '/');
    }
    const tabParam = params.get('tab');
    if (tabParam) {
      setActiveTab(tabParam);
      // Вкладку применяем, но из адреса НЕ удаляем: иначе F5 вернёт пользователя на
      // «Анализ персонажа». Параметр `analyze` выше удаляется намеренно — он
      // одноразовый, а вкладка это состояние экрана, и ей место в URL.
      window.history.replaceState({}, '', params.toString() ? `/?${params.toString()}` : '/');
    }
  }, []);

  useEffect(() => {
    if (!pendingAnalyzeUrl || isLoading || result || error) return;
    
    const urlToAnalyze = pendingAnalyzeUrl;
    setPendingAnalyzeUrl(null);
    setLastAnalyzedUrl(urlToAnalyze);
    analyze(decodeURIComponent(urlToAnalyze));
  }, [pendingAnalyzeUrl, isLoading, result, error, analyze]);

  const formatSnapshotName = (name: string, date: Date): string => {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${name} ${day}.${month}.${year} ${hours}:${minutes}`;
  };

  const handleTabChange = (_groupKey: string, tabKey: string) => {
    setActiveTab(tabKey);
  };

  useEffect(() => {
    if (result) {
      setCurrentResult(result);
      setLastAnalyzed(new Date());
      setActiveTab((prev) => (prev === 'track' ? 'track' : 'stats'));
      const params = new URLSearchParams(window.location.search);
      if (params.has('analyze')) {
        params.delete('analyze');
        window.history.replaceState({}, '', params.toString() ? `/?${params.toString()}` : '/');
      }
    }
  }, [result]);

  const handleLoadSnapshot = (data: Snapshot & Record<string, unknown>) => {
    // A46: раньше здесь стояло `as unknown as AnalysisResult` — слепок попадал
    // во вкладки анализа без проверки формы. Теперь проверяем и говорим, если
    // это не результат анализа.
    const parsed = asAnalysisResult(data);
    if (!parsed) {
      showToast('В слепке нет результата анализа — снимите новый слепок', 'error');
      return;
    }
    setCurrentResult(parsed);
    setLastAnalyzed(new Date(data.analyzed_at as string));
    setActiveTab((prev) => (prev === 'track' ? 'track' : 'stats'));
  };

  const handleSaveSnapshot = async () => {
    if (!currentResult) return;
    try {
      await saveSnapshot({
        snapshot_data: toPayload(currentResult),
        snapshot_name: snapshotName,
        url: '',
      });
      setShowSaveModal(false);
      setSnapshotName('');
    } catch {
      // ignore
    }
  };

  const handleAddToCompare = async () => {
    if (!currentResult) return;
    try {
      await addCompareCharacter(currentResult.name, currentResult);
      showToast(`Персонаж "${currentResult.name}" добавлен к сравнению`, 'success');
    } catch (err) {
      console.error('Add to compare error:', err);
      showToast('Ошибка при добавлении к сравнению', 'error');
    }
  };

  const handleToggleChat = useCallback(() => setChatOpen((prev) => !prev), []);

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
          {activeTab !== 'history' && activeTab !== 'compare' && activeTab !== 'closed' && (
            <CharacterPanel
              character={currentResult || undefined}
              lastAnalyzed={lastAnalyzed}
              onAnalyze={(url) => { setLastAnalyzedUrl(url); analyze(url); }}
              isLoading={isLoading}
              onSave={() => {
                const defaultName = currentResult?.name || 'Персонаж';
                setSnapshotName(formatSnapshotName(defaultName, new Date()));
                setShowSaveModal(true);
              }}
              onClear={() => { setCurrentResult(null); setLastAnalyzed(null); }}
              onAddToCompare={handleAddToCompare}
              onLoadSnapshot={handleLoadSnapshot}
              defaultExpanded={activeTab === 'stats'}
            />
          )}

          {isLoading && <LoadingSpinner />}

          {error && (
            <div className="error-banner">
              <p>{error}</p>
              <Button variant="ghost" onClick={() => { setCurrentResult(null); setLastAnalyzed(null); }}>Закрыть</Button>
            </div>
          )}
          {/* Персонаж закрыт или недоступен: полных данных с сайта нет, но слепки,
              снятые пока он был открыт, в базе остаются. Показываем их — иначе
              пользователю неоткуда взять информацию. Если слепков нет, компонент
              скажет об этом прямо. Закрытый профиль — НЕ ошибка: бэкенд отдаёт
              урезанный результат с profile_closed, поэтому проверяем и его.
              Блок отдельный, а не внутри баннера: баннер — flex-строка, и список встал бы
              сбоку от сообщения. */}
          {(error || result?.profile_closed) && snapshotNick && (
            <div className="error-snapshots">
              <p className="error-snapshots-note">
                {result?.profile_closed
                  ? 'Персонаж закрыт: с сайта доступна только основная информация.'
                  : 'Данные с сайта получить не удалось.'}{' '}
                Ниже — слепки персонажа «{snapshotNick}» из базы: если он раньше был
                открыт, выберите нужный.
              </p>
              <SnapshotHistory onLoad={handleLoadSnapshot} initialNick={snapshotNick} compact />
            </div>
          )}

          {!isLoading && activeTab !== 'export' && (
            <AnalysisResultDisplay result={currentResult} activeTab={activeTab} onLoadSnapshot={handleLoadSnapshot} />
          )}

          {activeTab === 'export' && <ExportTab currentResult={currentResult} />}

          {currentResult && <ScenarioComparison character={currentResult} />}

          <Modal
            isOpen={showSaveModal}
            onClose={() => { setShowSaveModal(false); setSnapshotName(''); }}
            title="Сохранить слепок"
          >
            <Input
              label="Имя слепка (необязательно)"
              value={snapshotName}
              onChange={(e) => setSnapshotName(e.target.value)}
              placeholder="Например: До рейда"
            />
            <div style={{ display: 'flex', gap: '8px', marginTop: '16px', justifyContent: 'flex-end' }}>
              <Button variant="ghost" onClick={() => { setShowSaveModal(false); setSnapshotName(''); }}>
                Отмена
              </Button>
              <Button variant="primary" onClick={handleSaveSnapshot}>
                Сохранить
              </Button>
            </div>
          </Modal>
        </main>
      </div>
      {chatOpen && <ClanChat onClose={() => setChatOpen(false)} />}
    </div>
  );
}

function ClanPageWrapper() {
  const { clanId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [chatOpen, setChatOpen] = useState(false);

  // Вкладка живёт в адресе — единственный источник истины. Раньше она дублировалась
  // состоянием, инициализированным из URL один раз: переход, меняющий только адрес
  // (например, из «Статуса персонажа» в конкретную пару), содержимое за собой не
  // двигал — на экране оставалась прежняя вкладка.
  const activeTab = new URLSearchParams(location.search).get('tab') || 'info';
  const activeGroup = TREASURY_TABS.includes(activeTab) ? 'treasury-nav' : 'clan';

  const handleToggleChat = useCallback(() => setChatOpen((prev) => !prev), []);

  // Переход из «Обзора клана» меняет адрес: и содержимое, и подсветка выводятся из
  // него. Состояние врозь с адресом здесь не живёт — иначе они расходятся.
  const handleSwitchTab = useCallback(
    (tab: string) => {
      const base = clanId ? `/clan/${clanId}` : location.pathname;
      navigate(`${base}?tab=${tab}`);
    },
    [navigate, clanId, location.pathname],
  );

  const renderContent = () => {
    if (activeGroup === 'clan' || activeGroup === 'treasury-nav') {
      switch (activeTab) {
        case 'info': return <ClanOverview clanId={Number(clanId) || DEFAULT_CLAN_ID} onSwitchTab={handleSwitchTab} />;
        case 'members': return <ClanMembersTable clanId={Number(clanId) || DEFAULT_CLAN_ID} />;
        case 'treasury': return <TreasuryTab clanId={Number(clanId) || DEFAULT_CLAN_ID} />;
        case 'treasury-import': return <TreasuryImport clanId={Number(clanId) || DEFAULT_CLAN_ID} />;
        case 'analytics': return <TreasuryAnalytics clanId={Number(clanId) || DEFAULT_CLAN_ID} />;
        case 'treasury-pairs': return <TreasuryPairsQueue clanId={Number(clanId) || DEFAULT_CLAN_ID} />;
        case 'member-status': return <MemberStatusTab clanId={Number(clanId) || DEFAULT_CLAN_ID} />;
        case 'loans': return <TreasuryLoansTab clanId={Number(clanId) || DEFAULT_CLAN_ID} />;
        case 'exclusions': return <TreasuryExclusionsTab clanId={Number(clanId) || DEFAULT_CLAN_ID} />;
      }
    }
    return null;
  };

  return (
    <div className="app">
      <Header />
      <div className="app-layout">
        <Sidebar
          activeTab={activeTab}
          chatOpen={chatOpen}
          onToggleChat={handleToggleChat}
        />
        <main className="main-content">
          <div className="clan-page-with-sidebar">
            <div className="clan-page-content">
              {renderContent()}
            </div>
          </div>
        </main>
      </div>
      {chatOpen && <ClanChat onClose={() => setChatOpen(false)} />}
    </div>
  );
}

export default function App() {
  return (
<BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/character"
          element={
            <ProtectedRoute>
              <CharacterPageWrapper />
            </ProtectedRoute>
          }
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <HomePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/about"
          element={
            <ProtectedRoute>
              <AboutPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
        <Route
          path="/clan/:clanId"
          element={
            <ProtectedRoute>
              <ClanPageWrapper />
            </ProtectedRoute>
          }
        />
      </Routes>
      <ToastProvider />
    </BrowserRouter>
  );
}
