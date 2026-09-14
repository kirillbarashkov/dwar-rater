import { useState, useEffect, useCallback, useMemo } from 'react';
import { getTreasuryOperations, getClanMembers, getLeftMembers } from '../../api/clanInfo';
import type { TreasuryOperationData, ClanMemberData } from '../../types/clanInfo';
import { usePermission } from '../../hooks/useAuth';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { buildMemberStatusByNick } from '../../utils/treasury';
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
  const isAdmin = usePermission('clan_info', 'admin') === 'full';
  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [members, setMembers] = useState<ClanMemberData[]>([]);
  const [leftMembers, setLeftMembers] = useState<{ nick: string }[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('tax');

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [opsData, membersData, leftData] = await Promise.all([
              getTreasuryOperations(clanId),
              getClanMembers(clanId).catch(() => []),
              getLeftMembers(clanId).catch(() => []),
            ]);
            setOperations(opsData);
            setMembers(membersData);
            setLeftMembers(leftData);
          } catch {
            setOperations([]);
            setMembers([]);
            setLeftMembers([]);
    } finally {
      setIsLoading(false);
    }
  }, [clanId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const memberStatusByNick = useMemo(
    () => buildMemberStatusByNick(members, leftMembers, operations.map((o) => o.nick)),
    [members, leftMembers, operations],
  );

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
                  <TaxAnalytics operations={operations} members={members} clanId={clanId} isAdmin={isAdmin} onRefresh={loadData} memberStatusByNick={memberStatusByNick} />
                )}
                {activeTab === 'talent' && <TalentAnalytics operations={operations} members={members} memberStatusByNick={memberStatusByNick} />}
                {activeTab === 'misc' && <MiscAnalytics operations={operations} memberStatusByNick={memberStatusByNick} />}
      </div>
    </div>
  );
}