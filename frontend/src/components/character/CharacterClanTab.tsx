import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import type { TreasuryOperationData, ClanMemberData } from '../../types/clanInfo';
import { getTreasuryOperations, getClanMembers, getLevelHistory, getTreasuryTotals } from '../../api/clanInfo';
import { useAuth } from '../../hooks/useAuth';
import {
  MONTHS_RU,
  parseDate,
  isTaxOperation,
  isTalentOperation,
  CLAN_TAX_NORM,
  TALENT_RESOURCE_GROUPS,
  getOriginalOwner,
} from '../../utils/treasury';
import { DEFAULT_CLAN_ID } from '../../utils/constants';
import './CharacterClanTab.css';

const DEFAULT_NORM = 10;

type TaxStatus = 'paid' | 'paid_delayed' | 'compensated' | 'not_paid' | 'future_member' | 'not_in_clan' | 'left_clan';

interface TaxInfo {
  status: TaxStatus;
  totalPaid: number;
  onTimePaid: number;
  delayedPaid: number;
  normAmount: number;
  isOver: boolean;
}

interface ResourceInfo {
  resourceName: string;
  submitted: number;
  status: 'submitted' | 'not_submitted';
}

const STATUS_LABELS: Record<TaxStatus, string> = {
  paid: 'Оплачено',
  paid_delayed: 'Оплачено с задержкой',
  compensated: 'Зачтено',
  not_paid: 'Не оплачено',
  future_member: 'Ещё не время платить',
  not_in_clan: 'Ещё не в клане',
  left_clan: 'Вышел из клана',
};

const STATUS_CLASSES: Record<TaxStatus, string> = {
  paid: 'char-clan-badge-paid',
  paid_delayed: 'char-clan-badge-delayed',
  compensated: 'char-clan-badge-compensated',
  not_paid: 'char-clan-badge-notpaid',
  future_member: 'char-clan-badge-future',
  not_in_clan: 'char-clan-badge-notin',
  left_clan: 'char-clan-badge-left',
};

export function CharacterClanTab({ clanId = DEFAULT_CLAN_ID }: { clanId?: number } = {}) {
  const { user } = useAuth();
  const myNick = user?.character_nick ?? '';

  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());

  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [members, setMembers] = useState<ClanMemberData[]>([]);
  // Итоги за всё время приходят отдельным агрегатом (см. totalAllTime): тянуть ради
  // двух чисел всю историю клана — 15 000+ строк ≈ 3,5 МБ — незачем.
  const [totals, setTotals] = useState<{ operation_type: string; object_name: string; total: number }[]>([]);
  const [levelHistory, setLevelHistory] = useState<Record<string, Array<{ date: string; old_level: number; new_level: number }>>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Первая загрузка — со спиннером, смена месяца — тихая: старые цифры остаются на
  // экране, пока не придут новые, иначе вкладка мигает на каждый клик по месяцу.
  const firstLoad = useRef(true);
  useEffect(() => {
    let cancelled = false;
    const silent = !firstLoad.current;
    firstLoad.current = false;
    if (!silent) setLoading(true);
    Promise.all([
      // Только выбранный месяц: вкладка работает по одному месяцу, а история целиком
      // — это 15 000+ строк ≈ 3,5 МБ.
      getTreasuryOperations(clanId, { month: selectedMonth, year: selectedYear }),
      getClanMembers(clanId),
      getLevelHistory(clanId),
    ])
      .then(([ops, mems, lvlHist]) => {
        if (cancelled) return;
        setOperations(ops);
        setMembers(mems);
        setLevelHistory(lvlHist);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.error ?? 'Ошибка загрузки данных клана');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; }
  }, [clanId, selectedMonth, selectedYear]);

  useEffect(() => {
    if (!myNick) return;
    let cancelled = false;
    getTreasuryTotals(clanId, myNick)
      .then((data) => { if (!cancelled) setTotals(data); })
      .catch(() => { if (!cancelled) setTotals([]); });
    return () => { cancelled = true; };
  }, [clanId, myNick]);

  const myNickLower = myNick.toLowerCase();
  const myMember = useMemo(() => members.find((m) => m.nick.toLowerCase() === myNickLower), [members, myNickLower]);
  const myLevel = myMember?.level ?? null;
  const myJoinDate = myMember?.join_date ?? '';
  const myTrialUntil = myMember?.trial_until ?? '';
  const myLeftDate = myMember?.left_date ?? '';

  const joinInfo = useMemo(() => {
    if (myJoinDate) {
      const match = myJoinDate.match(/(\d{2})\.(\d{2})\.(\d{4})/);
      if (match) return { month: parseInt(match[2], 10), year: parseInt(match[3], 10) };
    }
    if (myTrialUntil) {
      const match = myTrialUntil.match(/(\d{2})\.(\d{2})\.(\d{4})/);
      if (match) {
        const trialMonth = parseInt(match[2], 10);
        const trialYear = parseInt(match[3], 10);
        const trialDate = new Date(trialYear, trialMonth - 1, parseInt(match[1], 10));
        const nowDate = new Date();
        nowDate.setHours(0, 0, 0, 0);
        if (trialDate < nowDate) {
          const joinDate = new Date(trialDate);
          joinDate.setDate(joinDate.getDate() - 14);
          return { month: joinDate.getMonth() + 1, year: joinDate.getFullYear() };
        }
        return { month: trialMonth, year: trialYear };
      }
    }
    return null;
  }, [myJoinDate, myTrialUntil]);

  const isPaymentDue = useMemo(() => {
    if (!joinInfo) return true;
    if (selectedYear > joinInfo.year) return true;
    if (selectedYear === joinInfo.year && selectedMonth > joinInfo.month) return true;
    return false;
  }, [joinInfo, selectedYear, selectedMonth]);

  /** Дата выхода из клана — вторая граница окна участия. */
  const leftInfo = useMemo(() => {
    if (!myLeftDate) return null;
    const match = myLeftDate.match(/(\d{2})\.(\d{2})\.(\d{4})/);
    if (!match) return null;
    return { month: parseInt(match[2], 10), year: parseInt(match[3], 10) };
  }, [myLeftDate]);

  // Окно участия: до месяца вступления персонажа в клане ещё не было, после месяца
  // выхода — уже нет. Без этих границ вкладка называла ушедшего «Не оплачено» за
  // месяцы, когда его в клане не было.
  const monthIndex = selectedYear * 12 + selectedMonth;
  const isBeforeJoin = !!joinInfo && monthIndex < joinInfo.year * 12 + joinInfo.month;
  const isAfterLeft = !!leftInfo && monthIndex > leftInfo.year * 12 + leftInfo.month;
  const outsideWindow = isBeforeJoin || isAfterLeft;

  // A19: мемоизирован — иначе taxInfo пересчитывался на каждый рендер.
  const getLevelAtDate = useCallback((dateStr: string): number | null => {
    const history = levelHistory[myNickLower];
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
  }, [levelHistory, myNickLower]);

  const taxInfo = useMemo<TaxInfo | null>(() => {
    if (!myNick) return null;
    let onTime = 0;
    let delayed = 0;
    let compensation = 0;
    let hasCompensationFlag = false;
    let paymentDateStr = '';

    for (const op of operations) {
      if (!isTaxOperation(op) || op.quantity <= 0) continue;
      if (op.nick.toLowerCase() !== myNickLower) continue;
      const parsed = parseDate(op.date);
      if (!parsed || parsed.month !== selectedMonth || parsed.year !== selectedYear) continue;

      if (parsed.day <= 15) {
        onTime += op.quantity;
      } else {
        delayed += op.quantity;
      }
      if (op.compensation_flag) {
        compensation += op.quantity;
        hasCompensationFlag = true;
        paymentDateStr = op.date;
      }
    }

    const effectiveLevel = paymentDateStr ? getLevelAtDate(paymentDateStr) : myLevel;
    const normAmount = effectiveLevel ? (CLAN_TAX_NORM[effectiveLevel] ?? DEFAULT_NORM) : (myLevel ? (CLAN_TAX_NORM[myLevel] ?? DEFAULT_NORM) : DEFAULT_NORM);
    const totalPaid = onTime + delayed;

    let status: TaxStatus = 'not_paid';
    if (isBeforeJoin) {
      status = 'not_in_clan';
    } else if (isAfterLeft) {
      status = 'left_clan';
    } else if (!isPaymentDue) {
      status = 'future_member';
    } else if (hasCompensationFlag) {
      status = 'compensated';
    } else if (totalPaid >= normAmount) {
      status = onTime >= normAmount ? 'paid' : 'paid_delayed';
    }

    const isOver = totalPaid > normAmount || compensation >= normAmount;
    const effectiveDelayed = onTime >= normAmount ? 0 : delayed;

    return { status, totalPaid, onTimePaid: onTime, delayedPaid: effectiveDelayed, normAmount, isOver };
  }, [operations, myNick, myNickLower, selectedMonth, selectedYear, myLevel, isPaymentDue, isBeforeJoin, isAfterLeft, getLevelAtDate]);

  const resourceInfos = useMemo<ResourceInfo[]>(() => {
    if (!myNick) return [];
    const results: ResourceInfo[] = [];
    const allTalentResources = TALENT_RESOURCE_GROUPS.flatMap((g) => g.resources);

    for (const resourceName of allTalentResources) {
      let submitted = 0;
      for (const op of operations) {
        if (!isTalentOperation(op) || op.quantity <= 0) continue;
        if (op.object_name !== resourceName) continue;
        const parsed = parseDate(op.date);
        if (!parsed || parsed.month !== selectedMonth || parsed.year !== selectedYear) continue;

        let owner = op.nick;
        if (op.operation_type === 'Возвращено главой') {
          owner = getOriginalOwner(
            { operation_type: op.operation_type, object_name: op.object_name, nick: op.nick, quantity: op.quantity, date: op.date },
            operations
          );
        }
        if (owner.toLowerCase() === myNickLower) {
          submitted += op.quantity;
        }
      }
      results.push({
        resourceName,
        submitted,
        status: submitted > 0 ? 'submitted' : 'not_submitted',
      });
    }
    return results;
  }, [operations, myNick, myNickLower, selectedMonth, selectedYear]);

  // Сводка за всё время — из агрегата. Группы сумм разбираются теми же правилами,
  // что и операции: isTaxOperation/isTalentOperation остаются в одном месте, бэкенд
  // отдаёт только суммы по типу и объекту.
  const totalAllTime = useMemo(() => {
    let tax = 0;
    let resources = 0;
    for (const group of totals) {
      if (isTaxOperation(group)) {
        tax += group.total;
      } else if (isTalentOperation(group)) {
        resources += group.total;
      }
    }
    return { tax, resources };
  }, [totals]);

  const daysToDeadline = useMemo(() => {
    const today = new Date();
    const deadline = new Date(selectedYear, selectedMonth - 1, 15);
    const diff = Math.ceil((deadline.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    return diff;
  }, [selectedMonth, selectedYear]);

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

  if (loading) {
    return <div className="char-clan-tab"><div className="char-clan-loading">Загрузка данных клана...</div></div>;
  }

  if (error) {
    return (
      <div className="char-clan-tab">
        <div className="char-clan-error">{error}</div>
      </div>
    );
  }

  if (!myNick) {
    return (
      <div className="char-clan-tab">
        <div className="char-clan-empty">
          Персонаж не привязан к аккаунту. Укажите ник в <a href="/profile">профиле</a>.
        </div>
      </div>
    );
  }

  if (!myMember) {
    return (
      <div className="char-clan-tab">
        <div className="char-clan-empty">
          Персонаж «{myNick}» не найден в составе клана {clanId}. Если вы состоите в другом клане, этот раздел недоступен.
        </div>
      </div>
    );
  }

  return (
    <div className="char-clan-tab">
      {/* Месяц навигация */}
      <div className="char-clan-month-nav">
        <button className="char-clan-nav-btn" onClick={handlePrevMonth} title="Предыдущий месяц">←</button>
        <span className="char-clan-month-label">{MONTHS_RU[selectedMonth]} {selectedYear}</span>
        <button className="char-clan-nav-btn" onClick={handleNextMonth} title="Следующий месяц">→</button>
        {daysToDeadline >= 0 && daysToDeadline <= 15 && isPaymentDue && !outsideWindow && (
          <span className="char-clan-deadline">⏰ До дедлайна налога: {daysToDeadline} дн.</span>
        )}
      </div>

      {/* Налог */}
      {taxInfo && (
        <div className="char-clan-section">
          <h3 className="char-clan-section-title">💰 Налог</h3>
          <div className="char-clan-tax-summary">
            <div className="char-clan-tax-status">
              <span className={`char-clan-badge ${STATUS_CLASSES[taxInfo.status]}`}>
                {STATUS_LABELS[taxInfo.status]}
              </span>
              {taxInfo.isOver && <span className="char-clan-badge char-clan-badge-over">Сверх нормы</span>}
            </div>
            {outsideWindow ? (
              <div className="char-clan-tax-hint">
                {isBeforeJoin
                  ? `В ${MONTHS_RU[selectedMonth]} ${selectedYear} персонажа ещё не было в клане — налог за этот месяц не начисляется.`
                  : `Персонаж вышел из клана${myLeftDate ? ` ${myLeftDate}` : ''} — налог за этот месяц не начисляется.`}
              </div>
            ) : (
            <div className="char-clan-tax-details">
              <div className="char-clan-tax-row">
                <span className="char-clan-tax-label">Уплачено</span>
                <span className="char-clan-tax-value">{taxInfo.totalPaid} монет</span>
              </div>
              <div className="char-clan-tax-row">
                <span className="char-clan-tax-label">Норма</span>
                <span className="char-clan-tax-value">{taxInfo.normAmount} монет</span>
              </div>
              {taxInfo.onTimePaid > 0 && (
                <div className="char-clan-tax-row">
                  <span className="char-clan-tax-label">Вовремя</span>
                  <span className="char-clan-tax-value char-clan-tax-win">{taxInfo.onTimePaid}</span>
                </div>
              )}
              {taxInfo.delayedPaid > 0 && (
                <div className="char-clan-tax-row">
                  <span className="char-clan-tax-label">С задержкой</span>
                  <span className="char-clan-tax-value char-clan-tax-lose">{taxInfo.delayedPaid}</span>
                </div>
              )}
            </div>
            )}
          </div>
        </div>
      )}

      {/* Ресурсы талантов по 3 группам — только внутри окна участия */}
      {!outsideWindow && TALENT_RESOURCE_GROUPS.map((group) => {
        const groupResources = resourceInfos.filter((r) => group.resources.includes(r.resourceName));
        const hasAny = groupResources.some((r) => r.submitted > 0);
        return (
          <div key={group.name} className="char-clan-section">
            <h3 className="char-clan-section-title">{group.name}</h3>
            <table className="char-clan-resource-table">
              <thead>
                <tr>
                  <th>Ресурс</th>
                  <th className="char-clan-num-col">Сдано</th>
                  <th className="char-clan-status-col">Статус</th>
                </tr>
              </thead>
              <tbody>
                {groupResources.map((r) => (
                  <tr key={r.resourceName}>
                    <td className="char-clan-resource-name">{r.resourceName}</td>
                    <td className="char-clan-num-col">{r.submitted > 0 ? r.submitted : '—'}</td>
                    <td className="char-clan-status-col">
                      <span className={`char-clan-badge ${r.status === 'submitted' ? 'char-clan-badge-paid' : 'char-clan-badge-notpaid'}`}>
                        {r.status === 'submitted' ? 'Сдано' : 'Не сдавал'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!hasAny && <div className="char-clan-group-empty">Нет взносов в этом месяце</div>}
          </div>
        );
      })}

      {/* Сводка за всё время */}
      <div className="char-clan-section char-clan-summary">
        <h3 className="char-clan-section-title">📊 Сводка за всё время</h3>
        <div className="char-clan-summary-grid">
          <div className="char-clan-summary-card">
            <span className="char-clan-summary-label">Всего налога</span>
            <span className="char-clan-summary-value">{totalAllTime.tax} монет</span>
          </div>
          <div className="char-clan-summary-card">
            <span className="char-clan-summary-label">Всего ресурсов сдано</span>
            <span className="char-clan-summary-value">{totalAllTime.resources}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
