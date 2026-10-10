import { useMemo, useState, useEffect, useCallback } from 'react';
import type { TreasuryOperationData, TaxCarryoverMonth, ReasonCode } from '../../types/clanInfo';
import type { ClanMemberData } from '../../types/clanInfo';
import { parseDate, formatDateKey, CLAN_TAX_NORM, MONTHS_RU } from '../../utils/treasury';
import {
  createTreasuryCompensation,
  updateTreasuryOperation,
  getLevelHistory,
  getTaxCarryovers,
  recomputeTaxCarryovers,
  reviewTaxCarryover,
  bulkReviewTaxCarryovers,
} from '../../api/clanInfo';
import { copyText } from '../../utils/clipboard';
import { TaxCarryoverPanel } from './TaxCarryoverPanel';
import { ReassignButton } from './ReassignButton';
import { MonthCloseControl } from './MonthCloseControl';
import { BulkCompensationPanel } from './BulkCompensationPanel';
import { TreasurySummaryPanel } from './TreasurySummaryPanel';
import { HelpTip } from '../ui/HelpTip';
import { GuideSteps } from '../ui/GuideSteps';
import './TaxAnalytics.css';

interface TaxAnalyticsProps {
  operations: TreasuryOperationData[];
  members?: ClanMemberData[];
  clanId?: number;
  /** True when the user holds treasury:write (correct operations / зачёты). */
  canManage?: boolean;
  /** True when the user holds treasury:approve (carry-over decisions). */
  canApprove?: boolean;
  /** Reason codes served by the API (treasury journal) for correction dropdowns. */
  reasonCodes?: ReasonCode[];
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
  /** Confirmed carry-over from the previous month, credited to this month. */
  carriedIn: number;
  onTimePaid: number;
  delayedPaid: number;
  compensationAmount: number;
  compensationComment: string;
  status: 'paid' | 'paid_delayed' | 'compensated' | 'not_paid' | 'future_member';
  isOver: boolean;
  paymentStartMonth?: { month: number; year: number } | null;
  operationId?: number;
  /** The month's money row — what «перераспределить» moves. */
  paymentOpId?: number;
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

export function TaxAnalytics({ operations, members = [], clanId, canManage = false, canApprove = false, reasonCodes = [], onRefresh }: TaxAnalyticsProps) {
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
    status: '',
    hasCompensation: '',
  });
  const [mainSort, setMainSort] = useState<SortConfig>({ column: 'status', direction: 'asc' });
  const [notPaidSort, setNotPaidSort] = useState<SortConfig>({ column: 'nick', direction: 'asc' });
  const [compensatedSort, setCompensatedSort] = useState<SortConfig>({ column: 'nick', direction: 'asc' });
  const [paidDelayedSort, setPaidDelayedSort] = useState<SortConfig>({ column: 'nick', direction: 'asc' });
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [editingRow, setEditingRow] = useState<string | null>(null);
  const [editingData, setEditingData] = useState<{ quantity: number; compensationFlag: boolean; compensationComment: string } | null>(null);
  const [editReason, setEditReason] = useState('');
  // A frozen month (treasurer closed it) refuses writes server-side; the UI hides
  // the row actions so the treasurer is not offered an action that will 400.
  const [monthClosed, setMonthClosed] = useState(false);
  const [levelHistory, setLevelHistory] = useState<Record<string, Array<{ date: string; old_level: number; new_level: number }>>>({});

  useEffect(() => {
    if (!clanId) return;
    let cancelled = false;
    getLevelHistory(clanId)
      .then((data) => { if (!cancelled) setLevelHistory(data); })
      .catch((err) => { console.error('Failed to load level history:', err); if (!cancelled) setLevelHistory({}); });
    return () => { cancelled = true; };
  }, [clanId]);

  const [carryover, setCarryover] = useState<TaxCarryoverMonth | null>(null);

  const loadCarryover = useCallback(() => {
    if (!clanId) return () => {};
    let cancelled = false;
    getTaxCarryovers(clanId, selectedMonth, selectedYear)
      .then((data) => { if (!cancelled) setCarryover(data); })
      .catch((err) => {
        console.error('Failed to load tax carry-overs:', err);
        if (!cancelled) setCarryover(null);
      });
    return () => { cancelled = true; };
  }, [clanId, selectedMonth, selectedYear]);

  useEffect(() => loadCarryover(), [loadCarryover]);

  /** Confirmed credits flowing INTO the displayed month, keyed by nick. */
  const carriedByNick = useMemo(() => {
    const map: Record<string, number> = {};
    for (const inc of carryover?.incoming ?? []) {
      const key = inc.nick.toLowerCase();
      map[key] = (map[key] || 0) + inc.amount;
    }
    return map;
  }, [carryover]);

  const runCarryoverAction = async (action: () => Promise<unknown>) => {
    if (!clanId) return;
    setIsSaving(true);
    try {
      await action();
      setCarryover(await getTaxCarryovers(clanId, selectedMonth, selectedYear));
    } catch (err) {
      console.error('Carry-over action failed:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRecomputeCarryover = () =>
    runCarryoverAction(() =>
      recomputeTaxCarryovers(clanId as number, selectedMonth, selectedYear)
    );

  const handleReviewCarryover = (id: number, action: 'confirm' | 'cancel', comment?: string) =>
    runCarryoverAction(() =>
      reviewTaxCarryover(clanId as number, id, action, comment)
    );

  const handleBulkCarryover = (ids: number[], action: 'confirm' | 'cancel') =>
    runCarryoverAction(() => bulkReviewTaxCarryovers(clanId as number, ids, action));

  const getLevelAtDate = useCallback((nick: string, dateStr: string): number | null => {
    const nickLower = nick.toLowerCase();
    const history = levelHistory[nickLower];
    if (!history || history.length === 0) return null;

    const parsed = parseDate(dateStr);
    if (!parsed) return null;
    const targetTime = new Date(parsed.year, parsed.month - 1, parsed.day, parsed.hour || 0, parsed.minute || 0).getTime();

    let level: number | null = null;
    for (const event of history) {
      const eventParsed = parseDate(event.date);
      if (!eventParsed) continue;
      const eventTime = new Date(eventParsed.year, eventParsed.month - 1, eventParsed.day).getTime();
      if (eventTime <= targetTime) {
        level = event.new_level;
      } else {
        break;
      }
    }
    return level;
  }, [levelHistory]);

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
      } else if (m.trial_until) {
        const match = m.trial_until.match(/(\d{2})\.(\d{2})\.(\d{4})/);
        if (match) {
          const trialMonth = parseInt(match[2], 10);
          const trialYear = parseInt(match[3], 10);
          const trialDate = new Date(trialYear, trialMonth - 1, parseInt(match[1], 10));
          const now = new Date();
          now.setHours(0, 0, 0, 0);
          if (trialDate < now) {
            const joinDate = new Date(trialDate);
            joinDate.setDate(joinDate.getDate() - 14);
            map[m.nick.toLowerCase()] = {
              month: joinDate.getMonth() + 1,
              year: joinDate.getFullYear(),
            };
          } else {
            map[m.nick.toLowerCase()] = {
              month: trialMonth,
              year: trialYear,
            };
          }
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
    const paymentsByPlayer: Record<string, { onTime: number; delayed: number; compensation: number; opId: number; paymentOpId: number; flag: boolean; comment: string; originalNick: string }> = {};

    for (const p of taxPayments) {
      const parsed = parseDate(p.date);
      if (!parsed) continue;
      if (parsed.month !== selectedMonth || parsed.year !== selectedYear) continue;

      const key = p.nick.toLowerCase();
      if (!paymentsByPlayer[key]) {
        paymentsByPlayer[key] = { onTime: 0, delayed: 0, compensation: 0, opId: 0, paymentOpId: 0, flag: false, comment: '', originalNick: p.nick };
      }
      if (p.day <= 15) {
        paymentsByPlayer[key].onTime += p.amount;
      } else {
        paymentsByPlayer[key].delayed += p.amount;
      }
      if (!p.compensationFlag) {
        // The money row of the month. Tracked apart from opId, which stays the
        // compensation row's identity — a member can have both in one month.
        paymentsByPlayer[key].paymentOpId = p.operationId;
      }
      if (p.compensationFlag) {
        paymentsByPlayer[key].compensation += p.amount;
        paymentsByPlayer[key].opId = p.operationId;
        paymentsByPlayer[key].flag = p.compensationFlag;
        paymentsByPlayer[key].comment = p.compensationComment;
      }
    }

    const playerSummaries: PlayerTaxSummary[] = [];

    const addedNicks = new Set<string>();

    for (const [nickLower, data] of Object.entries(paymentsByPlayer)) {
      const currentLevel = memberLevels[nickLower];
      const paymentOp = data.opId ? operations.find(o => o.id === data.opId) : undefined;
      const levelAtPayment = paymentOp ? getLevelAtDate(data.originalNick, paymentOp.date) : null;
      const effectiveLevel = levelAtPayment ?? currentLevel;
      const normAmount = effectiveLevel ? (CLAN_TAX_NORM[effectiveLevel] ?? DEFAULT_NORM) : (memberNorms[nickLower] || DEFAULT_NORM);
      const totalPaid = data.onTime + data.delayed;
      const carriedIn = carriedByNick[nickLower] || 0;
      // «Зачёт» rows (compensation_flag) are bookkeeping markers, not money.
      // Counting them as income invents an overpayment — the same rule the
      // carry-over engine applies (shared/services/tax_engine.py::is_real_payment),
      // so the badge and the generated proposal can never disagree.
      const realPaid = totalPaid - data.compensation;
      const covered = realPaid + carriedIn;

      let status: PlayerTaxSummary['status'] = 'not_paid';
      if (!isPaymentDue(nickLower)) {
        status = 'future_member';
      } else if (data.flag) {
        status = 'compensated';
      } else if (covered >= normAmount) {
        status = data.onTime >= normAmount ? 'paid' : 'paid_delayed';
      }

      const isOver = covered > normAmount;
      const paymentStart = getPaymentStartMonth(nickLower);

      playerSummaries.push({
        nick: data.originalNick,
        playerLevel: effectiveLevel,
        normAmount,
        // В «Уплачено» идут ТОЛЬКО деньги: зачёт (compensation_flag) — bookkeeping-
        // маркер, а не поступление. Раньше сюда попадала сырая сумма вместе с
        // зачётом, и «Собрано» в шапке раздувалось на сумму зачётов — при том что
        // рядом в коде стоит ровно противоположный комментарий, а бэкенд
        // (tax_engine.is_real_payment) считает зачёт не деньгами.
        totalPaid: realPaid,
        carriedIn,
        onTimePaid: data.onTime,
        delayedPaid: data.onTime >= normAmount ? 0 : data.delayed,
        compensationAmount: data.compensation,
        compensationComment: data.comment,
        status,
        isOver,
        operationId: data.opId || undefined,
        paymentOpId: data.paymentOpId || undefined,
        paymentStartMonth: paymentStart,
      });
      addedNicks.add(nickLower);
    }

    for (const m of members) {
      const nickLower = m.nick.toLowerCase();
      if (!addedNicks.has(nickLower)) {
        const paymentStart = getPaymentStartMonth(nickLower);
        const isFuture = !isPaymentDue(nickLower);
        const memberNorm = getNormForLevel(m.level);
        const carriedIn = carriedByNick[nickLower] || 0;
        // A confirmed carry-over settles the month even without cash payments —
        // otherwise a covered member would be listed as a debtor.
        const coveredByCarry = !isFuture && carriedIn >= memberNorm;

        playerSummaries.push({
          nick: m.nick,
          playerLevel: m.level,
          normAmount: memberNorm,
          totalPaid: 0,
          carriedIn,
          onTimePaid: 0,
          delayedPaid: 0,
          compensationAmount: 0,
          compensationComment: '',
          status: isFuture ? 'future_member' : coveredByCarry ? 'paid' : 'not_paid',
          isOver: false,
          paymentStartMonth: paymentStart,
        });
        addedNicks.add(nickLower);
      }
    }

    playerSummaries.sort((a, b) => {
      const order = { paid: 0, paid_delayed: 1, compensated: 2, not_paid: 3, future_member: 4 };
      if (order[a.status] !== order[b.status]) {
        return order[a.status] - order[b.status];
      }
      return b.totalPaid - a.totalPaid;
    });

    const totalCollected = playerSummaries.reduce((sum, p) => sum + p.totalPaid, 0);
    const delayedTotal = playerSummaries.reduce((sum, p) => sum + p.delayedPaid, 0);
    const expectedTotal = playerSummaries.reduce((sum, p) => sum + (p.status === 'future_member' ? 0 : p.normAmount), 0);

    return {
      month: selectedMonth,
      year: selectedYear,
      players: playerSummaries,
      totalCollected,
      delayedTotal,
      expectedTotal,
    };
  }, [taxPayments, members, selectedMonth, selectedYear, memberLevels, memberNorms, getLevelAtDate, operations, carriedByNick]);

  const filteredPlayers = useMemo(() => {
    if (!monthSummary) return [];
    
    return monthSummary.players.filter(p => {
      if (filters.search && !p.nick.toLowerCase().includes(filters.search.toLowerCase())) {
        return false;
      }
      if (filters.level && p.playerLevel !== parseInt(filters.level)) {
        return false;
      }
      // «Переплата» — не статус, а флаг isOver: у человека статус «заплатил», но
      // внёс больше нормы. Отдельная ветка, иначе фильтр по статусу его не найдёт.
      if (filters.status === 'over' && !p.isOver) {
        return false;
      }
      if (filters.status && filters.status !== 'over' && p.status !== filters.status) {
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

  const paidDelayedPlayers = filteredPlayers.filter(p => p.status === 'paid_delayed');
  const compensatedPlayers = filteredPlayers.filter(p => p.status === 'compensated');
  const notPaidPlayers = filteredPlayers.filter(p => p.status === 'not_paid');
  const futureMemberPlayers = filteredPlayers.filter(p => p.status === 'future_member');
  const overpaidPlayers = filteredPlayers.filter(p => p.isOver);
  const paidOnTimePlayers = filteredPlayers.filter(p => p.status === 'paid' && !p.isOver);

  const totalExpected = monthSummary ? monthSummary.players.reduce((sum, p) => sum + (p.status === 'future_member' ? 0 : p.normAmount), 0) : 0;
  const totalCollected = monthSummary ? monthSummary.players.reduce((sum, p) => sum + p.totalPaid, 0) : 0;
  // «Не собрано» = РЕАЛЬНЫЙ дефицит: подтверждённый перенос закрывает месяц
  // (деньги пришли в прошлом месяце), поэтому он не считается недостачей.
  // Новички не должны ничего. Считаем по участникам: излишек одного не гасит
  // долг другого. Зачёт вычитается наравне с деньгами: он закрывает норму, не
  // принося денег, — ровно так же считает бэкенд (`compute_member_ledger`,
  // `debt = max(0, norm − (paid + compensation + carried_in))`). Без этого
  // участник с зачётом выглядел должником на всю норму.
  const totalNotCollected = monthSummary
    ? monthSummary.players.reduce(
        (sum, p) =>
          p.status === 'future_member'
            ? sum
            : sum + Math.max(0, p.normAmount - p.totalPaid - p.compensationAmount - p.carriedIn),
        0
      )
    : 0;
  const totalCarriedIn = Object.values(carriedByNick).reduce((sum, v) => sum + v, 0);

  // Суммы для очередей «требует внимания». Ноль в очереди — не информация, а
  // занятое место, поэтому очередь с нулём просто не рисуется.
  const notPaidSum = notPaidPlayers.reduce((sum, p) => sum + p.normAmount, 0);
  const delayedSum = paidDelayedPlayers.reduce((sum, p) => sum + p.totalPaid, 0);
  const overpaySum = overpaidPlayers.reduce((sum, p) => sum + (p.totalPaid - p.normAmount), 0);
  const compensatedNorm = compensatedPlayers.reduce((sum, p) => sum + p.normAmount, 0);
  const coveragePercent = totalExpected > 0 ? Math.round((totalCollected / totalExpected) * 100) : 0;

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

  const handleCopyTable = async (players: PlayerTaxSummary[], _title: string) => {
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
    
    const copied = await copyText(text);
    setCopyStatus(
      copied ? 'Скопировано!' : 'Не удалось скопировать — выделите таблицу вручную'
    );
    setTimeout(() => setCopyStatus(null), 2000);
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
    if (summary.carriedIn > 0 && summary.totalPaid < summary.normAmount && !summary.isOver) {
      return <span className="tax-badge tax-badge-carried">Зачтено переплатой</span>;
    }
    if (summary.isOver) {
      return <span className="tax-badge tax-badge-over">Переплата</span>;
    }
    if (summary.status === 'paid_delayed') {
      return <span className="tax-badge tax-badge-delayed">Оплатил с просрочкой</span>;
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

  const startInlineEdit = (player: PlayerTaxSummary) => {
    setEditingRow(player.nick);
    setEditReason('');
    setEditingData({
      quantity: player.totalPaid,
      compensationFlag: player.status === 'compensated',
      compensationComment: player.compensationComment || '',
    });
  };

  const cancelInlineEdit = () => {
    setEditingRow(null);
    setEditingData(null);
  };

  const saveInlineEdit = async (player: PlayerTaxSummary) => {
    // A compensated row is edited through its «зачёт» marker; every other row
    // through the month's money operation. `operationId` is only filled for
    // compensation rows, so using it alone made editing a normal payment a
    // silent no-op.
    const targetId =
      player.status === 'compensated' ? player.operationId : player.paymentOpId;
    if (!clanId || !editingData || !targetId) return;

    setIsSaving(true);
    try {
      await updateTreasuryOperation(clanId, targetId, {
        quantity: editingData.quantity,
        compensation_flag: editingData.compensationFlag,
        compensation_comment: editingData.compensationComment,
        reason: editReason || undefined,
      });

      setEditingRow(null);
      setEditingData(null);
      if (onRefresh) {
        onRefresh();
      }
    } catch (err) {
      console.error('Failed to save:', err);
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
        <MonthCloseControl
          clanId={clanId}
          month={selectedMonth}
          year={selectedYear}
          canApprove={canApprove}
          reasonCodes={reasonCodes}
          onChanged={setMonthClosed}
        />
      </header>

      {monthSummary && (
        <>
          <div className="tax-kpi">
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{totalExpected.toLocaleString()}</span>
              <span className="tax-kpi-label">
                <HelpTip term="expected">Ожидалось</HelpTip>
              </span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{totalCollected.toLocaleString()}</span>
              <span className="tax-kpi-label">
                <HelpTip term="collected">Собрано</HelpTip>
              </span>
            </div>
            <div className="tax-kpi-card tax-kpi-danger">
              <span className="tax-kpi-value">{totalNotCollected.toLocaleString()}</span>
              <span className="tax-kpi-label">
                <HelpTip term="missing">Не собрано</HelpTip>
              </span>
            </div>
          </div>

          {/* Полоса покрытия: одним взглядом видно, сколько начисленного уже в казне. */}
          <div className="tax-coverage">
            <div className="tax-coverage-bar">
              <i style={{ width: `${coveragePercent}%` }} />
            </div>
            <div className="tax-coverage-line">
              Собрано {totalCollected.toLocaleString()} из {totalExpected.toLocaleString()} · {coveragePercent}%
            </div>
            {(compensatedNorm > 0 || overpaySum > 0 || totalCarriedIn > 0) && (
              <div className="tax-coverage-note">
                Почему «собрано» не равно «ожидалось»: зачёт — не деньги, а пометка «взнос
                не нужен»; переплата — наоборот, деньги сверх нормы; перенос закрывает
                норму деньгами, которые пришли в прошлом месяце. Сходится так: ожидалось{' '}
                {totalExpected.toLocaleString()} ={' '}
                {[
                  `собрано ${totalCollected.toLocaleString()}`,
                  overpaySum > 0 ? `− переплата ${overpaySum.toLocaleString()}` : null,
                  compensatedNorm > 0 ? `+ зачтено ${compensatedNorm.toLocaleString()}` : null,
                  totalCarriedIn > 0 ? `+ перенос ${totalCarriedIn.toLocaleString()}` : null,
                  totalNotCollected > 0 ? `+ не собрано ${totalNotCollected.toLocaleString()}` : null,
                ]
                  .filter(Boolean)
                  .join(' ')}
                .
              </div>
            )}
          </div>

          {/* Исключения вперёд: очередь с нулём не рисуется — ноль не информация,
              а занятое место. Каждая строка кликабельна и фильтрует таблицу. */}
          <div className="tax-queues">
            {notPaidPlayers.length > 0 && (
              <button
                className="tax-queue tax-queue-danger"
                onClick={() => setFilters((f) => ({ ...f, status: 'not_paid' }))}
              >
                <span className="tax-queue-label">
                  <span className="tax-status-dot tax-status-notpaid" />
                  Не заплатили
                </span>
                <span className="tax-queue-value">
                  {notPaidPlayers.length} чел. · {notPaidSum.toLocaleString()} монет
                </span>
                <span className="tax-queue-go">показать ›</span>
              </button>
            )}
            {paidDelayedPlayers.length > 0 && (
              <button
                className="tax-queue"
                onClick={() => setFilters((f) => ({ ...f, status: 'paid_delayed' }))}
              >
                <span className="tax-queue-label">
                  <span className="tax-status-dot tax-status-delayed" />
                  Оплатили с просрочкой
                </span>
                <span className="tax-queue-value">
                  {paidDelayedPlayers.length} чел. · {delayedSum.toLocaleString()} монет
                </span>
                <span className="tax-queue-go">показать ›</span>
              </button>
            )}
            {overpaidPlayers.length > 0 && (
              <button
                className="tax-queue"
                onClick={() => setFilters((f) => ({ ...f, status: 'over' }))}
              >
                <span className="tax-queue-label">
                  <span className="tax-status-dot tax-status-over" />
                  Переплата — излишек переносится на следующий месяц
                </span>
                <span className="tax-queue-value">
                  {overpaidPlayers.length} чел. · +{overpaySum.toLocaleString()} монет
                </span>
                <span className="tax-queue-go">показать ›</span>
              </button>
            )}
            {futureMemberPlayers.length > 0 && (
              <button
                className="tax-queue tax-queue-muted"
                onClick={() => setFilters((f) => ({ ...f, status: 'future_member' }))}
              >
                <span className="tax-queue-label">
                  <span className="tax-status-dot" />
                  Новички — норма начнётся со следующего месяца
                </span>
                <span className="tax-queue-value">{futureMemberPlayers.length} чел. · долга нет</span>
                <span className="tax-queue-go">показать ›</span>
              </button>
            )}
            {filters.status !== '' && (
              <button
                className="tax-queue tax-queue-reset"
                onClick={() => setFilters((f) => ({ ...f, status: '' }))}
              >
                <span className="tax-queue-label">Фильтр включён — показаны не все</span>
                <span className="tax-queue-go">снять фильтр ›</span>
              </button>
            )}
          </div>

          {/* Справочная строка: то, что не является исключением, но должно быть под рукой.
              «Всего участников» — именно всего, а не «сколько попало под фильтр»:
              иначе после клика по очереди цифра начинает врать. */}
          <div className="tax-secondary">
            Всего участников: {monthSummary ? monthSummary.players.length : 0}
            {filteredPlayers.length !== (monthSummary ? monthSummary.players.length : 0) &&
              <> (показано: {filteredPlayers.length})</>}{' '}
            · заплатили в срок: {paidOnTimePlayers.length} · зачтено: {compensatedPlayers.length}
            {totalCarriedIn > 0 && <> · перенос из прошлого месяца: {totalCarriedIn.toLocaleString()}</>}
          </div>

          {/* Числа — первыми: казначей заходит узнать «сколько собрали и кто должен».
              Шаги-объяснения идут сразу за ними, а не перед: иначе инструкция
              отодвигает цифры за нижнюю границу экрана. */}
          <GuideSteps
            title={`Как проходит месяц — ${periodLabel}`}
            steps={[
              {
                text: 'Посмотрите три числа выше: «Ожидалось» — сколько должны собрать, «Собрано» — сколько реально пришло, «Не собрано» — сколько ещё недобрали.',
              },
              {
                text: 'Разберите должников: отфильтруйте список по «Не заплатил», напомните людям про взнос — или зачтите его, если так решил совет.',
                action: {
                  label: 'Показать должников',
                  onClick: () => setFilters((f) => ({ ...f, status: 'not_paid' })),
                },
              },
              {
                text: 'Сверьте переплату: лишние монеты переносятся на следующий месяц. Подтверждать перенос можно только после закрытия месяца.',
              },
              {
                text: 'Закройте прошедший месяц, когда цифры сойдутся: после закрытия правки и импорт задним числом перестанут проходить.',
              },
              {
                text: 'Скопируйте готовую сводку в клановый чат — блок «Сводка для чата» ниже.',
              },
            ]}
          />

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
              value={filters.status}
              onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
            >
              <option value="">Все статусы</option>
              <option value="paid">Заплатил</option>
              <option value="paid_delayed">Оплатил с просрочкой</option>
              <option value="not_paid">Не заплатил</option>
              <option value="over">Переплата</option>
              <option value="future_member">Новичок</option>
            </select>
            <select
              value={filters.hasCompensation}
              onChange={e => setFilters(f => ({ ...f, hasCompensation: e.target.value }))}
            >
              <option value="">Все</option>
              <option value="yes">С компенсацией</option>
              <option value="no">Без компенсации</option>
            </select>
            {(filters.search || filters.level || filters.status || filters.hasCompensation) && (
              <button
                className="tax-filter-clear"
                onClick={() => setFilters({ search: '', level: '', status: '', hasCompensation: '' })}
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
                    <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
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
                      <th>
                        <HelpTip term="carryover" marker={false} clickToToggle={false}>
                          Перенос
                        </HelpTip>
                      </th>
                      <th className="tax-sortable" onClick={() => handleSort('main', 'norm')}>
                        <HelpTip term="norm" marker={false} clickToToggle={false}>
                          Норма
                        </HelpTip>{' '}
                        {renderSortIcon('main', 'norm')}
                      </th>
                      <th className="tax-sortable" onClick={() => handleSort('main', 'status')}>Статус {renderSortIcon('main', 'status')}</th>
                      <th>
                        <HelpTip term="compensation" marker={false} clickToToggle={false}>
                          Компенсация
                        </HelpTip>
                      </th>
                      <th>Комментарий</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedFilteredPlayers.map((p, idx) => (
                      <tr key={p.nick}>
                        <td className="tax-rank">{idx + 1}</td>
                        <td className="tax-nick">{p.nick}</td>
                        <td>{p.playerLevel ?? '-'}</td>
                        {editingRow === p.nick ? (
                          <>
                            <td>
                              <input
                                type="number"
                                className="tax-edit-input"
                                value={editingData?.quantity ?? 0}
                                onChange={(e) => setEditingData(prev => prev ? { ...prev, quantity: parseInt(e.target.value) || 0 } : null)}
                                min="0"
                              />
                            </td>
                            <td
                              className={p.carriedIn > 0 ? 'tax-over' : ''}
                              title={p.carriedIn > 0 ? 'Зачтена переплата за прошлый месяц' : undefined}
                            >
                              {p.carriedIn > 0 ? p.carriedIn : '—'}
                            </td>
                            <td>{p.normAmount}</td>
                            <td>{renderStatusBadge(p)}</td>
                            <td>
                              <label className="tax-edit-checkbox">
                                <input
                                  type="checkbox"
                                  checked={editingData?.compensationFlag ?? false}
                                  onChange={(e) => setEditingData(prev => prev ? { ...prev, compensationFlag: e.target.checked } : null)}
                                />
                                Зачтено
                              </label>
                            </td>
                            <td>
                              <input
                                type="text"
                                className="tax-edit-input tax-edit-comment"
                                value={editingData?.compensationComment ?? ''}
                                onChange={(e) => setEditingData(prev => prev ? { ...prev, compensationComment: e.target.value } : null)}
                                placeholder="Комментарий"
                              />
                            </td>
                          </>
                        ) : (
                          <>
                            <td className={p.isOver ? 'tax-over' : 'tax-paid'}>{p.totalPaid}</td>
                            <td
                              className={p.carriedIn > 0 ? 'tax-over' : ''}
                              title={p.carriedIn > 0 ? 'Зачтена переплата за прошлый месяц' : undefined}
                            >
                              {p.carriedIn > 0 ? p.carriedIn : '—'}
                            </td>
                            <td>{p.normAmount}</td>
                            <td>{renderStatusBadge(p)}</td>
                            <td>
                              {canManage && p.status === 'not_paid' && (
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
                              {!canManage && p.status === 'compensated' && (
                                <span className="tax-compensated">Да</span>
                              )}
                            </td>
                            <td className="tax-comment-cell" title={p.compensationComment || undefined}>
                              {p.compensationComment || '-'}
                            </td>
                          </>
                        )}
                        <td className="tax-actions">
                          {canManage &&
                            !monthClosed &&
                            editingRow !== p.nick &&
                            (p.paymentOpId || p.operationId) && (
                            <button
                              className="tax-edit-btn"
                              onClick={() => startInlineEdit(p)}
                              title="Редактировать"
                            >
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                              </svg>
                            </button>
                          )}
                          {canManage && !monthClosed && editingRow !== p.nick && (
                            <ReassignButton
                              clanId={clanId}
                              operationId={p.paymentOpId}
                              nick={p.nick}
                              members={members}
                              reasonCodes={reasonCodes}
                              disabled={isSaving}
                              onDone={() => onRefresh?.()}
                            />
                          )}
                          {editingRow === p.nick && (
                            <>
                              <select
                                className="tax-edit-input tax-edit-reason"
                                value={editReason}
                                onChange={(e) => setEditReason(e.target.value)}
                                title="Причина правки — попадёт в журнал корректировок"
                              >
                                <option value="">Причина…</option>
                                {reasonCodes.map((r) => (
                                  <option key={r.code} value={r.code}>{r.label}</option>
                                ))}
                              </select>
                              <button
                                className="tax-save-btn"
                                onClick={() => saveInlineEdit(p)}
                                disabled={isSaving}
                                title="Сохранить"
                              >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <polyline points="20 6 9 17 4 12"/>
                                </svg>
                              </button>
                              <button
                                className="tax-cancel-btn"
                                onClick={cancelInlineEdit}
                                disabled={isSaving}
                                title="Отмена"
                              >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <line x1="18" y1="6" x2="6" y2="18"/>
                                  <line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                              </button>
                            </>
                          )}
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
                        void copyText([headers.join('\t'), rows].join('\n')).then((ok) => { setCopyStatus(ok ? 'Скопировано!' : 'Не удалось скопировать — выделите таблицу вручную'); setTimeout(() => setCopyStatus(null), 2000); });
                      }}
                      title="Копировать таблицу"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
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
                        void copyText([headers.join('\t'), rows].join('\n')).then((ok) => { setCopyStatus(ok ? 'Скопировано!' : 'Не удалось скопировать — выделите таблицу вручную'); setTimeout(() => setCopyStatus(null), 2000); });
                      }}
                      title="Копировать таблицу"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
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
                        void copyText([headers.join('\t'), rows].join('\n')).then((ok) => { setCopyStatus(ok ? 'Скопировано!' : 'Не удалось скопировать — выделите таблицу вручную'); setTimeout(() => setCopyStatus(null), 2000); });
                      }}
                      title="Копировать таблицу"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
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

      {/* Инструменты правки стоят ПОСЛЕ данных: казначей заходит узнать «сколько
          собрали и кто должен», а не «чем тут можно править». Пока они были
          сверху, цифры и таблица уезжали ниже первого экрана (замер: 610px
          инструментов, 1414px содержимого в окне 569px). Переезд в свои вкладки
          («Переносы», «Взносы» в режиме выделения) — следующий этап плана
          development-roadmap/treasury-ux-restructure-v1.0.md. */}
      <TaxCarryoverPanel
        month={selectedMonth}
        year={selectedYear}
        data={carryover}
        canApprove={canApprove}
        isSaving={isSaving}
        onRecompute={handleRecomputeCarryover}
        onReview={handleReviewCarryover}
        onBulk={handleBulkCarryover}
      />

      <BulkCompensationPanel
        clanId={clanId}
        canManage={canManage}
        members={members}
        month={selectedMonth}
        year={selectedYear}
      />

      <TreasurySummaryPanel clanId={clanId} month={selectedMonth} year={selectedYear} />

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