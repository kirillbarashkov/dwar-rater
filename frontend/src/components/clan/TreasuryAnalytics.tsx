import { useState, useEffect, useCallback } from 'react';
import { getTreasuryOperations, getClanMembers, getTreasuryJournal } from '../../api/clanInfo';
import type { TreasuryOperationData, ClanMemberData, ReasonCode } from '../../types/clanInfo';
import { MONTHS_RU } from '../../utils/treasury';
import { usePermission } from '../../hooks/useAuth';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { TaxAnalytics } from './TaxAnalytics';
import { TaxLedger } from './TaxLedger';
import { TalentAnalytics } from './TalentAnalytics';
import { MiscAnalytics } from './MiscAnalytics';
import { TreasuryJournal } from './TreasuryJournal';
import { TreasuryAnomalies } from './TreasuryAnomalies';
import { NickTransferPanel } from './NickTransferPanel';
import { MonthCloseControl } from './MonthCloseControl';
import './TreasuryAnalytics.css';

interface TreasuryAnalyticsProps {
  clanId: number;
}

type TabType = 'overview' | 'dues' | 'ledger' | 'carryover' | 'resources' | 'audit';

/**
 * Порядок вкладок — по рабочему циклу казначея: сначала «как дела» (Обзор), потом
 * работа со взносами и переносами, потом справочное (Сальдо, ресурсы), и в конце
 * служебное (Аудит). Диагностика и журнал — два под-уровня одной вкладки: и то и
 * другое отвечает на вопрос «кто и что изменил», просто с разных сторон.
 */
const TABS: { key: TabType; label: string }[] = [
  { key: 'overview', label: 'Обзор' },
  { key: 'dues', label: 'Взносы' },
  { key: 'ledger', label: 'Сальдо' },
  { key: 'carryover', label: 'Переносы' },
  { key: 'resources', label: 'Ресурсы и прочее' },
  { key: 'audit', label: 'Аудит' },
];

export function TreasuryAnalytics({ clanId }: TreasuryAnalyticsProps) {
  // Treasury edits are their own permission (a «Казначей» must be able to
  // correct operations without clan-member import rights).
  const canManage = usePermission('treasury', 'write') === 'full';
  // Set by a click on an «unknown nick» finding: it prefills the transfer panel
  // right below, so the diagnostic and its remedy sit together.
  const [transferFrom, setTransferFrom] = useState('');
  // Approving carry-over proposals is a separate decision right.
  const canApprove = usePermission('treasury', 'approve') === 'full';
  // The journal is treasurer-level: who corrected what is not public clan data.
  const canReadJournal = usePermission('treasury', 'read') === 'full';
  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [members, setMembers] = useState<ClanMemberData[]>([]);
  const [reasonCodes, setReasonCodes] = useState<ReasonCode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  // Второй уровень «Аудита»: диагностика находок и журнал правок.
  const [auditTab, setAuditTab] = useState<'diagnostics' | 'journal'>('diagnostics');
  // Период раздела — один на все вкладки: иначе «Налоги» и «Переносы» показывают
  // разные месяцы, и это читается как ошибка в цифрах, а не как разные фильтры.
  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState<number>(now.getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState<number>(now.getFullYear());
  // A frozen month (treasurer closed it) refuses writes server-side; the UI hides
  // the row actions so the treasurer is not offered an action that will 400.
  const [monthClosed, setMonthClosed] = useState(false);

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

  const periodLabel = `${MONTHS_RU[selectedMonth]} ${selectedYear}`;

  const handlePrevMonth = () => {
    if (selectedMonth === 1) {
      setSelectedMonth(12);
      setSelectedYear((y) => y - 1);
    } else {
      setSelectedMonth((m) => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (selectedMonth === 12) {
      setSelectedMonth(1);
      setSelectedYear((y) => y + 1);
    } else {
      setSelectedMonth((m) => m + 1);
    }
  };

  return (
    <div className="treasury-analytics">
      <header className="treasury-analytics-header">
        <h2 className="treasury-analytics-title">Аналитика казны</h2>
        {/* Период задаётся один раз здесь и наследуется вкладками. */}
        <div className="tax-period-nav">
          <button onClick={handlePrevMonth} title="Предыдущий месяц">←</button>
          <span className="tax-period-label">{periodLabel}</span>
          <button onClick={handleNextMonth} title="Следующий месяц">→</button>
        </div>
        <MonthCloseControl
          clanId={clanId}
          month={selectedMonth}
          year={selectedYear}
          canApprove={canApprove}
          reasonCodes={reasonCodes}
          onChanged={setMonthClosed}
        />
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
        {/* Один TaxAnalytics на три вкладки. Между «Обзором», «Взносами» и
            «Переносами» он не размонтируется (условие и key неизменны), поэтому
            расчётная цепочка одна и фильтры при переключении не сбрасываются. */}
        {(activeTab === 'overview' || activeTab === 'dues' || activeTab === 'carryover') && (
          <TaxAnalytics
            key="treasury-tax"
            view={activeTab}
            operations={operations}
            members={members}
            clanId={clanId}
            canManage={canManage}
            canApprove={canApprove}
            reasonCodes={reasonCodes}
            onRefresh={loadData}
            month={selectedMonth}
            year={selectedYear}
            monthClosed={monthClosed}
          />
        )}
        {activeTab === 'ledger' && <TaxLedger clanId={clanId} />}
        {activeTab === 'resources' && (
          <>
            <TalentAnalytics operations={operations} members={members} />
            <MiscAnalytics operations={operations} />
          </>
        )}
        {activeTab === 'audit' && (
          <>
            <nav className="ta-subtabs">
              <button
                className={`ta-subtab ${auditTab === 'diagnostics' ? 'ta-subtab-active' : ''}`}
                onClick={() => setAuditTab('diagnostics')}
              >
                Диагностика
              </button>
              {canReadJournal && (
                <button
                  className={`ta-subtab ${auditTab === 'journal' ? 'ta-subtab-active' : ''}`}
                  onClick={() => setAuditTab('journal')}
                >
                  Журнал правок
                </button>
              )}
            </nav>
            {auditTab === 'diagnostics' && (
              <>
                <TreasuryAnomalies clanId={clanId} canManage={canManage} onPickNick={setTransferFrom} />
                {canManage && (
                  <NickTransferPanel clanId={clanId} canManage={canManage} fromNick={transferFrom} />
                )}
              </>
            )}
            {auditTab === 'journal' && canReadJournal && (
              <TreasuryJournal clanId={clanId} canManage={canManage} reasonCodes={reasonCodes} />
            )}
          </>
        )}
      </div>
    </div>
  );
}