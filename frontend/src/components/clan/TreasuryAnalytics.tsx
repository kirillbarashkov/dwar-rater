import { useState, useEffect, useCallback } from 'react';
import { getTreasuryOperations, getClanMembers } from '../../api/clanInfo';
import type { TreasuryOperationData, ClanMemberData } from '../../types/clanInfo';
import { useAuth } from '../../hooks/useAuth';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { TaxAnalytics } from './TaxAnalytics';
import { TalentAnalytics } from './TalentAnalytics';
import { MiscAnalytics } from './MiscAnalytics';
import './TreasuryAnalytics.css';

interface TreasuryAnalyticsProps {
  clanId: number;
}

type TabType = 'tax' | 'talent' | 'misc';

const TABS: { key: TabType; label: string }[] = [
  { key: 'tax', label: 'Налоги' },
  { key: 'talent', label: 'Ресурсы талантов' },
  { key: 'misc', label: 'Прочее' },
];

export function TreasuryAnalytics({ clanId }: TreasuryAnalyticsProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [members, setMembers] = useState<ClanMemberData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('tax');

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [opsData, membersData] = await Promise.all([
        getTreasuryOperations(clanId),
        getClanMembers(clanId).catch(() => []),
      ]);
      setOperations(opsData);
      setMembers(membersData);
    } catch {
      setOperations([]);
      setMembers([]);
    } finally {
      setIsLoading(false);
    }
  }, [clanId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="treasury-analytics">
      <header className="treasury-analytics-header">
        <h2 className="treasury-analytics-title">Аналитика казны</h2>
      </header>

      <nav className="ta-tabs">
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={`ta-tab ${activeTab === tab.key ? 'ta-tab-active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="ta-tab-content">
        {activeTab === 'tax' && (
          <TaxAnalytics operations={operations} members={members} clanId={clanId} isAdmin={isAdmin} onRefresh={loadData} />
        )}
        {activeTab === 'talent' && <TalentAnalytics operations={operations} />}
        {activeTab === 'misc' && <MiscAnalytics operations={operations} />}
      </div>
    </div>
  );
}