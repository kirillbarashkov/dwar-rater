import { useState, useEffect, useCallback } from 'react';
import { getTreasuryOperations, getClanMembers, getTreasuryJournal } from '../../api/clanInfo';
import type { TreasuryOperationData, ClanMemberData, ReasonCode } from '../../types/clanInfo';
import { usePermission } from '../../hooks/useAuth';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { TaxAnalytics } from './TaxAnalytics';
import { TaxLedger } from './TaxLedger';
import { TalentAnalytics } from './TalentAnalytics';
import { MiscAnalytics } from './MiscAnalytics';
import { TreasuryJournal } from './TreasuryJournal';
import './TreasuryAnalytics.css';

interface TreasuryAnalyticsProps {
  clanId: number;
}

type TabType = 'tax' | 'ledger' | 'talent' | 'misc' | 'journal';

const TABS: { key: TabType; label: string }[] = [
  { key: 'tax', label: 'Налоги' },
  { key: 'ledger', label: 'Сальдо' },
  { key: 'talent', label: 'Ресурсы талантов' },
  { key: 'misc', label: 'Прочее' },
  { key: 'journal', label: 'Журнал' },
];

export function TreasuryAnalytics({ clanId }: TreasuryAnalyticsProps) {
  // Treasury edits are their own permission (a «Казначей» must be able to
  // correct operations without clan-member import rights).
  const canManage = usePermission('treasury', 'write') === 'full';
  // Approving carry-over proposals is a separate decision right.
  const canApprove = usePermission('treasury', 'approve') === 'full';
  // The journal is treasurer-level: who corrected what is not public clan data.
  const canReadJournal = usePermission('treasury', 'read') === 'full';
  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [members, setMembers] = useState<ClanMemberData[]>([]);
  const [reasonCodes, setReasonCodes] = useState<ReasonCode[]>([]);
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

  // Reason codes come from the API (one source of truth for the dropdowns).
  useEffect(() => {
    if (!canReadJournal) return;
    let cancelled = false;
    getTreasuryJournal(clanId, { limit: 1 })
      .then((data) => {
        if (!cancelled) setReasonCodes(data.reason_codes);
      })
      .catch(() => {
        if (!cancelled) setReasonCodes([]);
      });
    return () => {
      cancelled = true;
    };
  }, [clanId, canReadJournal]);

  if (isLoading) return <LoadingSpinner />;

  const visibleTabs = TABS.filter((tab) => tab.key !== 'journal' || canReadJournal);

  return (
    <div className="treasury-analytics">
      <header className="treasury-analytics-header">
        <h2 className="treasury-analytics-title">Аналитика казны</h2>
      </header>

      <nav className="ta-tabs">
        {visibleTabs.map(tab => (
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
        {activeTab === 'ledger' && <TaxLedger clanId={clanId} />}
        {activeTab === 'tax' && (
          <TaxAnalytics
            operations={operations}
            members={members}
            clanId={clanId}
            canManage={canManage}
            canApprove={canApprove}
            reasonCodes={reasonCodes}
            onRefresh={loadData}
          />
        )}
        {activeTab === 'talent' && <TalentAnalytics operations={operations} members={members} />}
        {activeTab === 'misc' && <MiscAnalytics operations={operations} />}
        {activeTab === 'journal' && canReadJournal && (
          <TreasuryJournal clanId={clanId} canManage={canManage} reasonCodes={reasonCodes} />
        )}
      </div>
    </div>
  );
}