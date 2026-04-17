import { useMemo, useState } from 'react';
import type { TreasuryOperationData } from '../../types/clanInfo';
import type { ClanMemberData } from '../../types/clanInfo';
import { parseDate, formatDateKey, CLAN_TAX_NORM, MONTHS_RU } from '../../utils/treasury';
import { createTreasuryCompensation } from '../../api/clanInfo';
import './TaxAnalytics.css';

interface TaxAnalyticsProps {
  operations: TreasuryOperationData[];
  members?: ClanMemberData[];
  clanId?: number;
  isAdmin?: boolean;
  onRefresh?: () => void;
}

interface TaxPayment {
  nick: string;
  amount: number;
  date: string;
  day: number;
  operationId: number;
  compensationFlag: boolean;
  compensationComment: string;
}

interface PlayerTaxSummary {
  nick: string;
  playerLevel?: number;
  normAmount: number;
  totalPaid: number;
  onTimePaid: number;
  delayedPaid: number;
  compensationAmount: number;
  compensationComment: string;
  status: 'paid' | 'paid_delayed' | 'compensated' | 'not_paid' | 'future_member';
  isOver: boolean;
  paymentStartMonth?: { month: number; year: number } | null;
}

interface MonthSummary {
  month: number;
  year: number;
  players: PlayerTaxSummary[];
  totalCollected: number;
  delayedTotal: number;
  expectedTotal: number;
}

type SortDirection = 'asc' | 'desc';

interface SortConfig {
  column: string | null;
  direction: SortDirection;
}

const DEFAULT_NORM = 10;

function getNormForLevel(level: number): number {
  return CLAN_TAX_NORM[level] || DEFAULT_NORM;
}

export function TaxAnalytics({ operations, members = [], clanId, isAdmin = false, onRefresh }: TaxAnalyticsProps) {
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [editingCompensation, setEditingCompensation] = useState<{
    nick: string;
    level: number;
    normAmount: number;
  } | null>(null);
  const [compensationComment, setCompensationComment] = useState('');
  const [selectedMonths, setSelectedMonths] = useState<number[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [filters, setFilters] = useState({
    search: '',
    level: '',
    norm: '',
    status: '',
    hasCompensation: '',
  });
  const [mainSort, setMainSort] = useState<SortConfig>({ column: 'status', direction: 'asc' });
  const [notPaidSort, setNotPaidSort] = useState<SortConfig>({ column: 'nick', direction: 'asc' });
  const [compensatedSort, setCompensatedSort] = useState<SortConfig>({ column: 'nick', direction: 'asc' });
  const [paidDelayedSort, setPaidDelayedSort] = useState<SortConfig>({ column: 'nick', direction: 'asc' });
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  const memberLevels = useMemo(() => {
    const map: Record<string, number> = {};
    for (const m of members) {
      map[m.nick.toLowerCase()] = m.level;
    }
    return map;
  }, [members]);

  const memberNorms = useMemo(() => {
    const map: Record<string, number> = {};
    for (const m of members) {
      map[m.nick.toLowerCase()] = getNormForLevel(m.level);
    }
    return map;
  }, [members]);

  const memberJoinDates = useMemo(() => {
    const map: Record<string, { month: number; year: number } | null> = {};
    for (const m of members) {
      if (m.join_date) {
        const match = m.join_date.match(/(\d{2})\.(\d{2})\.(\d{4})/);
        if (match) {
          map[m.nick.toLowerCase()] = {
            month: parseInt(match[2], 10),
            year: parseInt(match[3], 10),
          };
        }
      } else {
        map[m.nick.toLowerCase()] = null;
      }
    }
    return map;
  }, [members]);

  const getMinCompensationMonth = (nick: string): number | null => {
    const joinInfo = memberJoinDates[nick.toLowerCase()];
    if (!joinInfo) return null;
    
    const currentYear = new Date().getFullYear();
    const currentMonth = new Date().getMonth() + 1;
    
    if (joinInfo.year < currentYear) {
      return null;
    }
    
    if (joinInfo.year === currentYear) {
      if (joinInfo.month === currentMonth) {
        const nextMonth = currentMonth + 1;
        return nextMonth <= 12 ? nextMonth : null;
      }
      return joinInfo.month;
    }
    
    return null;
  };

  const getPaymentStartMonth = (nick: string): { month: number; year: number } | null => {
    const joinInfo = memberJoinDates[nick.toLowerCase()];
    if (!joinInfo) return null;
    
    if (joinInfo.month === 12) {
      return { month: 1, year: joinInfo.year + 1 };
    }
    return { month: joinInfo.month + 1, year: joinInfo.year };
  };

  const isPaymentDue = (nick: string): boolean => {
    const joinInfo = memberJoinDates[nick.toLowerCase()];
    if (!joinInfo) return true;
    
    if (selectedYear > joinInfo.year) return true;
    if (selectedYear === joinInfo.year && selectedMonth > joinInfo.month) return true;
    return false;
  };

  const taxPayments = useMemo(() => {
    const payments: TaxPayment[] = [];

    for (const op of operations) {
      if (op.operation_type !== 'Деньги' || op.object_name !== 'Монеты') continue;
      if (op.quantity <= 0) continue;

      const parsed = parseDate(op.date);
      if (!parsed) continue;

      payments.push({
        nick: op.nick,
        amount: op.quantity,
        date: formatDateKey(parsed.day, parsed.month, parsed.year),
        day: parsed.day,
        operationId: op.id,
        compensationFlag: op.compensation_flag,
        compensationComment: op.compensation_comment,
      });
    }

    return payments;
  }, [operations]);

  const monthSummary = useMemo((): MonthSummary | null => {
    const paymentsByPlayer: Record<string, { onTime: number; delayed: number; compensation: number; opId: number; flag: boolean; comment: string }> = {};

    for (const p of taxPayments) {
      const parsed = parseDate(p.date);
      if (!parsed) continue;
      if (parsed.month !== selectedMonth || parsed.year !== selectedYear) continue;

      const key = p.nick.toLowerCase();
      if (!paymentsByPlayer[key]) {
        paymentsByPlayer[key] = { onTime: 0, delayed: 0, compensation: 0, opId: 0, flag: false, comment: '' };
      }
      if (p.day <= 15) {
        paymentsByPlayer[key].onTime += p.amount;
      } else {
        paymentsByPlayer[key].delayed += p.amount;
      }
      if (p.compensationFlag) {
        paymentsByPlayer[key].compensation += p.amount;
        paymentsByPlayer[key].opId = p.operationId;
        paymentsByPlayer[key].flag = p.compensationFlag;
        paymentsByPlayer[key].comment = p.compensationComment;
      }
    }

    const playerSummaries: PlayerTaxSummary[] = [];

    for (const [nickLower, data] of Object.entries(paymentsByPlayer)) {
      const level = memberLevels[nickLower];
      const normAmount = memberNorms[nickLower] || DEFAULT_NORM;
      const totalPaid = data.onTime + data.delayed;

      let status: PlayerTaxSummary['status'] = 'not_paid';
      if (data.flag) {
        status = 'compensated';
      } else if (totalPaid >= normAmount) {
        status = data.delayed > 0 ? 'paid_delayed' : 'paid';
      }

      const isOver = totalPaid > normAmount || data.compensation >= normAmount;

      const displayNick = nickLower.charAt(0).toUpperCase() + nickLower.slice(1);
      playerSummaries.push({
        nick: displayNick,
        playerLevel: level,
        normAmount,
        totalPaid,
        onTimePaid: data.onTime,
        delayedPaid: data.delayed,
        compensationAmount: data.compensation,
        compensationComment: data.comment,
        status,
        isOver,
      });
    }

    const paidNicks = new Set(playerSummaries.filter(p => p.status !== 'not_paid' && p.status !== 'future_member').map(p => p.nick.toLowerCase()));

    for (const m of members) {
      const nickLower = m.nick.toLowerCase();
      if (!paidNicks.has(nickLower)) {
        const paymentStart = getPaymentStartMonth(nickLower);
        const isFuture = !isPaymentDue(nickLower);
        
        playerSummaries.push({
          nick: m.nick,
          playerLevel: m.level,
          normAmount: getNormForLevel(m.level),
          totalPaid: 0,
          onTimePaid: 0,
          delayedPaid: 0,
          compensationAmount: 0,
          compensationComment: '',
          status: isFuture ? 'future_member' : 'not_paid',
          isOver: false,
          paymentStartMonth: paymentStart,
        });
      }
    }

    playerSummaries.sort((a, b) => {
      const order = { paid: 0, paid_delayed: 1, compensated: 2, not_paid: 3, future_member: 4 };
      if (order[a.status] !== order[b.status]) {
        return order[a.status] - order[b.status];
      }
      return b.totalPaid - a.totalPaid;
    });

    const totalCollected = Object.values(paymentsByPlayer).reduce((sum, v) => sum + v.onTime + v.delayed, 0);
    const delayedTotal = Object.values(paymentsByPlayer).reduce((sum, v) => sum + v.delayed, 0);
    const expectedTotal = playerSummaries.reduce((sum, p) => sum + (p.status === 'future_member' ? 0 : p.normAmount), 0);

    return {
      month: selectedMonth,
      year: selectedYear,
      players: playerSummaries,
      totalCollected,
      delayedTotal,
      expectedTotal,
    };
  }, [taxPayments, members, selectedMonth, selectedYear, memberLevels, memberNorms]);

  const filteredPlayers = useMemo(() => {
    if (!monthSummary) return [];
    
    return monthSummary.players.filter(p => {
      if (filters.search && !p.nick.toLowerCase().includes(filters.search.toLowerCase())) {
        return false;
      }
      if (filters.level && p.playerLevel !== parseInt(filters.level)) {
        return false;
      }
      if (filters.norm && p.normAmount !== parseInt(filters.norm)) {
        return false;
      }
      if (filters.status && p.status !== filters.status) {
        return false;
      }
      if (filters.hasCompensation === 'yes' && p.status !== 'compensated') {
        return false;
      }
      if (filters.hasCompensation === 'no' && p.status === 'compensated') {
        return false;
      }
      return true;
    });
  }, [monthSummary, filters]);

  const uniqueLevels = useMemo(() => {
    if (!monthSummary) return [];
    const levels = new Set(monthSummary.players.map(p => p.playerLevel).filter(l => l !== undefined) as number[]);
    return Array.from(levels).sort((a, b) => a - b);
  }, [monthSummary]);

  const uniqueNorms = useMemo(() => {
    if (!monthSummary) return [];
    const norms = new Set(monthSummary.players.map(p => p.normAmount));
    return Array.from(norms).sort((a, b) => a - b);
  }, [monthSummary]);

  const paidDelayedPlayers = filteredPlayers.filter(p => p.status === 'paid_delayed');
  const compensatedPlayers = filteredPlayers.filter(p => p.status === 'compensated');
  const notPaidPlayers = filteredPlayers.filter(p => p.status === 'not_paid');
  const futureMemberPlayers = filteredPlayers.filter(p => p.status === 'future_member');
  const overpaidPlayers = filteredPlayers.filter(p => p.isOver);
  const paidOnTimePlayers = filteredPlayers.filter(p => p.status === 'paid' && !p.isOver);

  const totalExpected = monthSummary.players.reduce((sum, p) => sum + (p.status === 'future_member' ? 0 : p.normAmount), 0);
  const totalCollected = monthSummary.players.reduce((sum, p) => sum + p.totalPaid, 0);
  const totalNotCollected = Math.max(0, totalExpected - totalCollected);

  const sortedFilteredPlayers = useMemo(() => {
    if (!mainSort.column) return filteredPlayers;
    
    return [...filteredPlayers].sort((a, b) => {
      let cmp = 0;
      switch (mainSort.column) {
        case 'nick':
          cmp = a.nick.localeCompare(b.nick);
          break;
        case 'level':
          cmp = (a.playerLevel || 0) - (b.playerLevel || 0);
          break;
        case 'paid':
          cmp = b.totalPaid - a.totalPaid;
          break;
        case 'norm':
          cmp = a.normAmount - b.normAmount;
          break;
        case 'status':
          const statusOrder: Record<string, number> = { paid: 0, paid_delayed: 1, compensated: 2, not_paid: 3, future_member: 4 };
          cmp = (statusOrder[a.status] || 5) - (statusOrder[b.status] || 5);
          break;
      }
      return mainSort.direction === 'asc' ? cmp : -cmp;
    });
  }, [filteredPlayers, mainSort]);

  const sortedNotPaidPlayers = useMemo(() => {
    if (!notPaidSort.column) return notPaidPlayers;
    return [...notPaidPlayers].sort((a, b) => {
      let cmp = 0;
      switch (notPaidSort.column) {
        case 'nick':
          cmp = a.nick.localeCompare(b.nick);
          break;
        case 'level':
          cmp = (a.playerLevel || 0) - (b.playerLevel || 0);
          break;
        case 'norm':
          cmp = a.normAmount - b.normAmount;
          break;
      }
      return notPaidSort.direction === 'asc' ? cmp : -cmp;
    });
  }, [notPaidPlayers, notPaidSort]);

  const sortedCompensatedPlayers = useMemo(() => {
    if (!compensatedSort.column) return compensatedPlayers;
    return [...compensatedPlayers].sort((a, b) => {
      let cmp = 0;
      switch (compensatedSort.column) {
        case 'nick':
          cmp = a.nick.localeCompare(b.nick);
          break;
        case 'level':
          cmp = (a.playerLevel || 0) - (b.playerLevel || 0);
          break;
        case 'norm':
          cmp = a.normAmount - b.normAmount;
          break;
      }
      return compensatedSort.direction === 'asc' ? cmp : -cmp;
    });
  }, [compensatedPlayers, compensatedSort]);

  const sortedPaidDelayedPlayers = useMemo(() => {
    if (!paidDelayedSort.column) return paidDelayedPlayers;
    return [...paidDelayedPlayers].sort((a, b) => {
      let cmp = 0;
      switch (paidDelayedSort.column) {
        case 'nick':
          cmp = a.nick.localeCompare(b.nick);
          break;
        case 'level':
          cmp = (a.playerLevel || 0) - (b.playerLevel || 0);
          break;
        case 'paid':
          cmp = b.totalPaid - a.totalPaid;
          break;
      }
      return paidDelayedSort.direction === 'asc' ? cmp : -cmp;
    });
  }, [paidDelayedPlayers, paidDelayedSort]);

  const handleSort = (table: 'main' | 'notPaid' | 'compensated' | 'paidDelayed', column: string) => {
    const setSort = table === 'main' ? setMainSort : table === 'notPaid' ? setNotPaidSort : table === 'compensated' ? setCompensatedSort : setPaidDelayedSort;
    const currentSort = table === 'main' ? mainSort : table === 'notPaid' ? notPaidSort : table === 'compensated' ? compensatedSort : paidDelayedSort;
    
    if (currentSort.column === column) {
      setSort({ column, direction: currentSort.direction === 'asc' ? 'desc' : 'asc' });
    } else {
      setSort({ column, direction: 'desc' });
    }
  };

  const renderSortIcon = (table: 'main' | 'notPaid' | 'compensated' | 'paidDelayed', column: string) => {
    const currentSort = table === 'main' ? mainSort : table === 'notPaid' ? notPaidSort : table === 'compensated' ? compensatedSort : paidDelayedSort;
    if (currentSort.column !== column) return <span className="tax-sort-icon">↕</span>;
    return <span className="tax-sort-icon tax-sort-active">{currentSort.direction === 'asc' ? '↑' : '↓'}</span>;
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'paid': return 'Заплатил';
      case 'paid_delayed': return 'Заплатил + Задержано';
      case 'compensated': return 'Зачтено';
      case 'not_paid': return 'Не заплатил';
      case 'future_member': return 'Оплата с';
      default: return status;
    }
  };

  const handleCopyTable = async (players: PlayerTaxSummary[], title: string) => {
    if (players.length === 0) return;
    
    const headers = ['#', 'Игрок', 'Уровень', 'Уплачено', 'Норма', 'Статус', 'Комментарий'];
    const rows = players.map((p, idx) => [
      idx + 1,
      p.nick,
      p.playerLevel ?? '-',
      p.totalPaid,
      p.normAmount,
      getStatusLabel(p.status),
      p.compensationComment || ''
    ].join('\t')).join('\n');
    
    const text = [headers.join('\t'), rows].join('\n');
    
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus('Скопировано!');
      setTimeout(() => setCopyStatus(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
      setCopyStatus('Ошибка копирования');
      setTimeout(() => setCopyStatus(null), 2000);
    }
  };

  const renderStatusBadge = (summary: PlayerTaxSummary) => {
    if (summary.status === 'future_member') {
      const ps = summary.paymentStartMonth;
      const dateStr = ps ? `01.${ps.month.toString().padStart(2, '0')}.${ps.year}` : '';
      return <span className="tax-badge tax-badge-future">Оплата с {dateStr}</span>;
    }
    if (summary.status === 'not_paid') {
      return <span className="tax-badge tax-badge-notpaid">Не заплатил</span>;
    }
    if (summary.status === 'compensated') {
      return <span className="tax-badge tax-badge-compensated">Зачтено</span>;
    }
    if (summary.isOver) {
      return <span className="tax-badge tax-badge-over">Заплатил + Сверхнормы</span>;
    }
    if (summary.status === 'paid_delayed') {
      return <span className="tax-badge tax-badge-delayed">Заплатил + Задержано</span>;
    }
    return <span className="tax-badge tax-badge-paid">Заплатил</span>;
  };

  const periodLabel = monthSummary
    ? `${MONTHS_RU[monthSummary.month]} ${monthSummary.year}`
    : '';

  const handlePrevMonth = () => {
    if (selectedMonth === 1) {
      setSelectedMonth(12);
      setSelectedYear(y => y - 1);
    } else {
      setSelectedMonth(m => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (selectedMonth === 12) {
      setSelectedMonth(1);
      setSelectedYear(y => y + 1);
    } else {
      setSelectedMonth(m => m + 1);
    }
  };

  const handleCompensate = (nick: string, level: number, normAmount: number) => {
    setEditingCompensation({ nick, level, normAmount });
    setCompensationComment('');
    setSelectedMonths([]);
  };

  const handleSaveCompensation = async () => {
    if (!editingCompensation || !clanId || selectedMonths.length === 0) return;

    setIsSaving(true);
    try {
      await createTreasuryCompensation(
        clanId,
        editingCompensation.nick,
        editingCompensation.normAmount,
        compensationComment,
        selectedMonths,
        selectedYear
      );

      setEditingCompensation(null);
      if (onRefresh) {
        onRefresh();
      }
    } catch (err) {
      console.error('Failed to save compensation:', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="tax-analytics">
      <header className="tax-header">
        <h2 className="tax-title">Аналитика налогов</h2>
        <div className="tax-period-nav">
          <button onClick={handlePrevMonth}>←</button>
          <span className="tax-period-label">{periodLabel}</span>
          <button onClick={handleNextMonth}>→</button>
        </div>
      </header>

      {monthSummary && (
        <>
          <div className="tax-kpi">
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{totalExpected.toLocaleString()}</span>
              <span className="tax-kpi-label">Ожидалось</span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{totalCollected.toLocaleString()}</span>
              <span className="tax-kpi-label">Собрано</span>
            </div>
            <div className="tax-kpi-card tax-kpi-danger">
              <span className="tax-kpi-value">{totalNotCollected.toLocaleString()}</span>
              <span className="tax-kpi-label">Не собрано</span>
            </div>
          </div>

          <div className="tax-kpi tax-kpi-row2">
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{filteredPlayers.length}</span>
              <span className="tax-kpi-label">Всего</span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{overpaidPlayers.length}</span>
              <span className="tax-kpi-label">Заплатил+сверхнормы</span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{paidOnTimePlayers.length}</span>
              <span className="tax-kpi-label">Заплатил</span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{paidDelayedPlayers.length}</span>
              <span className="tax-kpi-label">Заплатил+задержано</span>
            </div>
            <div className="tax-kpi-card tax-kpi-danger">
              <span className="tax-kpi-value">{notPaidPlayers.length}</span>
              <span className="tax-kpi-label">Не заплатил</span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{compensatedPlayers.length}</span>
              <span className="tax-kpi-label">Зачтено</span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{futureMemberPlayers.length}</span>
              <span className="tax-kpi-label">Новичок</span>
            </div>
          </div>

          <div className="tax-filters">
            <input
              type="text"
              className="tax-filter-search"
              placeholder="Поиск по игроку..."
              value={filters.search}
              onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
            />
            <select
              value={filters.level}
              onChange={e => setFilters(f => ({ ...f, level: e.target.value }))}
            >
              <option value="">Все уровни</option>
              {uniqueLevels.map(l => (
                <option key={l} value={l}>Ур. {l}</option>
              ))}
            </select>
            <select
              value={filters.norm}
              onChange={e => setFilters(f => ({ ...f, norm: e.target.value }))}
            >
              <option value="">Все нормы</option>
              {uniqueNorms.map(n => (
                <option key={n} value={n}>{n} монет</option>
              ))}
            </select>
            <select
              value={filters.status}
              onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
            >
              <option value="">Все статусы</option>
              <option value="paid">Заплатил</option>
              <option value="paid_delayed">Заплатил + Задержано</option>
              <option value="not_paid">Не заплатил</option>
            </select>
            <select
              value={filters.hasCompensation}
              onChange={e => setFilters(f => ({ ...f, hasCompensation: e.target.value }))}
            >
              <option value="">Все</option>
              <option value="yes">С компенсацией</option>
              <option value="no">Без компенсации</option>
            </select>
            {(filters.search || filters.level || filters.norm || filters.status || filters.hasCompensation) && (
              <button
                className="tax-filter-clear"
                onClick={() => setFilters({ search: '', level: '', norm: '', status: '', hasCompensation: '' })}
              >
                Сбросить
              </button>
            )}
          </div>

          <div className="tax-shortlists">
            <section className="tax-section tax-section-wide">
              <div className="tax-section-header">
                <h3 className="tax-section-title">Сводная — {periodLabel}</h3>
                <div className="tax-section-actions">
                  {copyStatus && <span className="tax-copy-status">{copyStatus}</span>}
                  <button 
                    className="tax-copy-btn" 
                    onClick={() => handleCopyTable(sortedFilteredPlayers, 'Сводная')}
                    title="Копировать таблицу"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                  </button>
                </div>
              </div>
              {sortedFilteredPlayers.length > 0 ? (
                <div className="tax-table-wrapper">
                <table className="tax-table">
                  <thead>
                    <tr>
                      <th className="tax-sortable">#</th>
                      <th className="tax-sortable" onClick={() => handleSort('main', 'nick')}>Игрок {renderSortIcon('main', 'nick')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('main', 'level')}>Уровень {renderSortIcon('main', 'level')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('main', 'paid')}>Уплачено {renderSortIcon('main', 'paid')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('main', 'norm')}>Норма {renderSortIcon('main', 'norm')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('main', 'status')}>Статус {renderSortIcon('main', 'status')}</th>
                      <th>Компенсация</th>
                      <th>Комментарий</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedFilteredPlayers.map((p, idx) => (
                      <tr key={p.nick}>
                        <td className="tax-rank">{idx + 1}</td>
                        <td className="tax-nick">{p.nick}</td>
                        <td>{p.playerLevel ?? '-'}</td>
                        <td className={p.isOver ? 'tax-over' : 'tax-paid'}>{p.totalPaid}</td>
                        <td>{p.normAmount}</td>
                        <td>{renderStatusBadge(p)}</td>
                        <td>
                          {isAdmin && p.status === 'not_paid' && (
                            <button
                              className="tax-compensate-btn"
                              onClick={() => handleCompensate(p.nick, p.playerLevel || 1, p.normAmount)}
                            >
                              Зачесть
                            </button>
                          )}
                          {p.status === 'compensated' && (
                            <span className="tax-compensated">Зачтено</span>
                          )}
                          {!isAdmin && p.status === 'compensated' && (
                            <span className="tax-compensated">Да</span>
                          )}
                        </td>
                        <td className="tax-comment-cell" title={p.compensationComment || undefined}>
                          {p.compensationComment || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              ) : (
                <div className="tax-empty">Нет данных за период</div>
              )}
            </section>

            <section className="tax-section">
              <div className="tax-section-header">
                <h3 className="tax-section-title">
                  <span className="tax-status-dot tax-status-notpaid" />
                  Не заплатил ({sortedNotPaidPlayers.length})
                </h3>
                {sortedNotPaidPlayers.length > 0 && (
                  <div className="tax-section-actions">
                    <button 
                      className="tax-copy-btn" 
                      onClick={() => {
                        const headers = ['Игрок', 'Уровень', 'Норма'];
                        const rows = sortedNotPaidPlayers.map(p => [p.nick, p.playerLevel ?? '-', p.normAmount].join('\t')).join('\n');
                        navigator.clipboard.writeText([headers.join('\t'), rows].join('\n')).then(() => { setCopyStatus('Скопировано!'); setTimeout(() => setCopyStatus(null), 2000); });
                      }}
                      title="Копировать таблицу"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                      </svg>
                    </button>
                  </div>
                )}
              </div>
              {sortedNotPaidPlayers.length > 0 ? (
                <div className="tax-table-wrapper">
                <table className="tax-table">
                  <thead>
                    <tr>
                      <th className="tax-sortable" onClick={() => handleSort('notPaid', 'nick')}>Игрок {renderSortIcon('notPaid', 'nick')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('notPaid', 'level')}>Уровень {renderSortIcon('notPaid', 'level')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('notPaid', 'norm')}>Норма {renderSortIcon('notPaid', 'norm')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedNotPaidPlayers.map(p => (
                      <tr key={p.nick}>
                        <td className="tax-nick">{p.nick}</td>
                        <td>{p.playerLevel ?? '-'}</td>
                        <td className="tax-debt">{p.normAmount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              ) : (
                <div className="tax-empty">Нет должников</div>
              )}
            </section>

            {compensatedPlayers.length > 0 && (
              <section className="tax-section">
                <div className="tax-section-header">
                  <h3 className="tax-section-title">
                    <span className="tax-status-dot tax-status-compensated" />
                    Зачтено ({sortedCompensatedPlayers.length})
                  </h3>
                  <div className="tax-section-actions">
                    <button 
                      className="tax-copy-btn" 
                      onClick={() => {
                        const headers = ['Игрок', 'Уровень', 'Сумма'];
                        const rows = sortedCompensatedPlayers.map(p => [p.nick, p.playerLevel ?? '-', p.normAmount].join('\t')).join('\n');
                        navigator.clipboard.writeText([headers.join('\t'), rows].join('\n')).then(() => { setCopyStatus('Скопировано!'); setTimeout(() => setCopyStatus(null), 2000); });
                      }}
                      title="Копировать таблицу"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                      </svg>
                    </button>
                  </div>
                </div>
                <div className="tax-table-wrapper">
                <table className="tax-table">
                  <thead>
                    <tr>
                      <th className="tax-sortable" onClick={() => handleSort('compensated', 'nick')}>Игрок {renderSortIcon('compensated', 'nick')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('compensated', 'level')}>Уровень {renderSortIcon('compensated', 'level')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('compensated', 'norm')}>Сумма {renderSortIcon('compensated', 'norm')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedCompensatedPlayers.map(p => (
                      <tr key={p.nick}>
                        <td className="tax-nick">{p.nick}</td>
                        <td>{p.playerLevel ?? '-'}</td>
                        <td className="tax-paid">{p.normAmount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </section>
            )}

            {paidDelayedPlayers.length > 0 && (
              <section className="tax-section">
                <div className="tax-section-header">
                  <h3 className="tax-section-title">
                    <span className="tax-status-dot tax-status-delayed" />
                    Заплатил + Задержано ({sortedPaidDelayedPlayers.length})
                  </h3>
                  <div className="tax-section-actions">
                    <button 
                      className="tax-copy-btn" 
                      onClick={() => {
                        const headers = ['Игрок', 'Уровень', 'Уплачено'];
                        const rows = sortedPaidDelayedPlayers.map(p => [p.nick, p.playerLevel ?? '-', p.totalPaid].join('\t')).join('\n');
                        navigator.clipboard.writeText([headers.join('\t'), rows].join('\n')).then(() => { setCopyStatus('Скопировано!'); setTimeout(() => setCopyStatus(null), 2000); });
                      }}
                      title="Копировать таблицу"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                      </svg>
                    </button>
                  </div>
                </div>
                <div className="tax-table-wrapper">
                <table className="tax-table">
                  <thead>
                    <tr>
                      <th className="tax-sortable" onClick={() => handleSort('paidDelayed', 'nick')}>Игрок {renderSortIcon('paidDelayed', 'nick')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('paidDelayed', 'level')}>Уровень {renderSortIcon('paidDelayed', 'level')}</th>
                      <th className="tax-sortable" onClick={() => handleSort('paidDelayed', 'paid')}>Уплачено {renderSortIcon('paidDelayed', 'paid')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedPaidDelayedPlayers.map(p => (
                      <tr key={p.nick}>
                        <td className="tax-nick">{p.nick}</td>
                        <td>{p.playerLevel ?? '-'}</td>
                        <td className="tax-paid">{p.totalPaid}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </section>
            )}
          </div>
        </>
      )}

      {editingCompensation && (
        <div className="tax-modal-overlay">
          <div className="tax-modal">
            <h3 className="tax-modal-title">Компенсация</h3>
            <div className="tax-modal-content">
              <p><strong>{editingCompensation.nick}</strong> (ур. {editingCompensation.level})</p>
              <p>Норма: {editingCompensation.normAmount} монет за месяц</p>
              <div className="tax-modal-months">
                {(() => {
                  const minMonth = getMinCompensationMonth(editingCompensation.nick);
                  const joinInfo = memberJoinDates[editingCompensation.nick.toLowerCase()];
                  return (
                    <>
                      <p>
                        {minMonth !== null
                          ? `Вступил: ${joinInfo ? MONTHS_RU[joinInfo.month] + ' ' + joinInfo.year : 'неизвестно'}. Доступны месяцы с ${MONTHS_RU[minMonth]}.`
                          : 'Выберите месяцы для компенсации:'}
                      </p>
                      <div className="tax-modal-months-grid">
                        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(month => {
                          const isDisabled = minMonth !== null && month < minMonth;
                          return (
                            <label 
                              key={month} 
                              className={`tax-modal-month-checkbox ${isDisabled ? 'tax-modal-month-disabled' : ''}`}
                            >
                              <input
                                type="checkbox"
                                checked={selectedMonths.includes(month)}
                                disabled={isDisabled}
                                onChange={e => {
                                  if (e.target.checked) {
                                    setSelectedMonths(prev => [...prev, month].sort((a, b) => a - b));
                                  } else {
                                    setSelectedMonths(prev => prev.filter(m => m !== month));
                                  }
                                }}
                              />
                              {MONTHS_RU[month]}
                            </label>
                          );
                        })}
                      </div>
                    </>
                  );
                })()}
              </div>
              <textarea
                className="tax-modal-textarea"
                placeholder="Комментарий (причина зачета)"
                value={compensationComment}
                onChange={e => setCompensationComment(e.target.value)}
              />
            </div>
            <div className="tax-modal-actions">
              <button
                className="tax-modal-btn tax-modal-btn-cancel"
                onClick={() => setEditingCompensation(null)}
                disabled={isSaving}
              >
                Отмена
              </button>
              <button
                className="tax-modal-btn tax-modal-btn-save"
                onClick={handleSaveCompensation}
                disabled={isSaving || selectedMonths.length === 0}
              >
                {isSaving ? 'Сохранение...' : `Сохранить (${selectedMonths.length})`}
              </button>
            </div>
          </div>
        </div>
      )}

      {!monthSummary && (
        <div className="tax-empty">Нет данных по налогам</div>
      )}
    </div>
  );
}