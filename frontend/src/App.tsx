import { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { useCharacterAnalysis } from './hooks/useCharacterAnalysis';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
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
import { saveSnapshot } from './api/snapshots';
import { addCompareCharacter } from './api/compare';
import type { AnalysisResult } from './types/character';
import type { Snapshot } from './types/snapshot';
import { LoginPage } from './pages/auth/LoginPage';
import { AdminPage } from './pages/admin/AdminPage';
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
  const [activeTab, setActiveTab] = useState('stats');
  const [pendingAnalyzeUrl, setPendingAnalyzeUrl] = useState<string | null>(null);
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
  }, []);

  useEffect(() => {
    if (!pendingAnalyzeUrl || isLoading || result || error) return;
    
    const urlToAnalyze = pendingAnalyzeUrl;
    setPendingAnalyzeUrl(null);
    analyze(decodeURIComponent(urlToAnalyze));
  }, [pendingAnalyzeUrl, isLoading, result, error, analyze]);

  useEffect(() => {
    if (result) {
      setCurrentResult(result);
      setLastAnalyzed(new Date());
      setActiveTab('stats');
    }
  }, [result]);

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
      setActiveTab('stats');
      const params = new URLSearchParams(window.location.search);
      if (params.has('analyze')) {
        params.delete('analyze');
        window.history.replaceState({}, '', params.toString() ? `/?${params.toString()}` : '/');
      }
    }
  }, [result]);

  const handleLoadSnapshot = (data: Snapshot & Record<string, unknown>) => {
    setCurrentResult(data as unknown as AnalysisResult);
    setLastAnalyzed(new Date(data.analyzed_at as string));
    setActiveTab('stats');
  };

  const handleSaveSnapshot = async () => {
    if (!currentResult) return;
    try {
      await saveSnapshot({
        snapshot_data: currentResult as unknown as Record<string, unknown>,
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
          {activeTab !== 'history' && activeTab !== 'track' && activeTab !== 'compare' && activeTab !== 'closed' && (
            <CharacterPanel
              character={currentResult || undefined}
              lastAnalyzed={lastAnalyzed}
              onAnalyze={(url) => analyze(url)}
              isLoading={isLoading}
              onSave={() => {
                const defaultName = currentResult?.name || 'Персонаж';
                setSnapshotName(formatSnapshotName(defaultName, new Date()));
                setShowSaveModal(true);
              }}
              onClear={() => { setCurrentResult(null); setLastAnalyzed(null); }}
              onAddToCompare={handleAddToCompare}
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

          {!isLoading && (
            <AnalysisResultDisplay result={currentResult} activeTab={activeTab} onLoadSnapshot={handleLoadSnapshot} />
          )}

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
  const [chatOpen, setChatOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('info');
  const [activeGroup, setActiveGroup] = useState('clan');

  const handleToggleChat = useCallback(() => setChatOpen((prev) => !prev), []);

  const handleTabChange = (groupKey: string, tabKey: string) => {
    setActiveGroup(groupKey);
    setActiveTab(tabKey);
  };

  const handleSwitchTab = useCallback((tab: string) => {
    setActiveTab(tab);
  }, []);

  const renderContent = () => {
    if (activeGroup === 'clan') {
      switch (activeTab) {
        case 'info': return <ClanOverview clanId={Number(clanId) || 2315} onSwitchTab={handleSwitchTab} />;
        case 'members': return <ClanMembersTable clanId={Number(clanId) || 2315} />;
        case 'treasury': return <TreasuryTab clanId={Number(clanId) || 2315} />;
        case 'treasury-import': return <TreasuryImport clanId={Number(clanId) || 2315} />;
        case 'analytics': return <TreasuryAnalytics clanId={Number(clanId) || 2315} />;
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
          onTabChange={handleTabChange}
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
          path="/"
          element={
            <ProtectedRoute>
              <HomePage />
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
