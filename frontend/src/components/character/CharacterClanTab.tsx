import { useState, useEffect, useMemo } from 'react';
import type { TreasuryOperationData, ClanMemberData } from '../../types/clanInfo';
import { getTreasuryOperations, getClanMembers, getLevelHistory } from '../../api/clanInfo';
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
import './CharacterClanTab.css';

const CLAN_ID = 2315;
const DEFAULT_NORM = 10;

type TaxStatus = 'paid' | 'paid_delayed' | 'compensated' | 'not_paid' | 'future_member';

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
};

const STATUS_CLASSES: Record<TaxStatus, string> = {
  paid: 'char-clan-badge-paid',
  paid_delayed: 'char-clan-badge-delayed',
  compensated: 'char-clan-badge-compensated',
  not_paid: 'char-clan-badge-notpaid',
  future_member: 'char-clan-badge-future',
};

export function CharacterClanTab() {
  const { user } = useAuth();
  const myNick = user?.character_nick ?? '';

  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());

  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [members, setMembers] = useState<ClanMemberData[]>([]);
  const [levelHistory, setLevelHistory] = useState<Record<string, Array<{ date: string; old_level: number; new_level: number }>>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getTreasuryOperations(CLAN_ID),
      getClanMembers(CLAN_ID),
      getLevelHistory(CLAN_ID),
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
    return () => { cancelled = true; };
  }, []);

  const myNickLower = myNick.toLowerCase();
  const myMember = useMemo(() => members.find((m) => m.nick.toLowerCase() === myNickLower), [members, myNickLower]);
  const myLevel = myMember?.level ?? null;
  const myJoinDate = myMember?.join_date ?? '';
  const myTrialUntil = myMember?.trial_until ?? '';

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

  const getLevelAtDate = (dateStr: string): number | null => {
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
  };

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
    if (!isPaymentDue) {
      status = 'future_member';
    } else if (hasCompensationFlag) {
      status = 'compensated';
    } else if (totalPaid >= normAmount) {
      status = delayed > 0 ? 'paid_delayed' : 'paid';
    }

    const isOver = totalPaid > normAmount || compensation >= normAmount;

    return { status, totalPaid, onTimePaid: onTime, delayedPaid: delayed, normAmount, isOver };
  }, [operations, myNick, myNickLower, selectedMonth, selectedYear, myLevel, isPaymentDue]);

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

  const totalAllTime = useMemo(() => {
    if (!myNick) return { tax: 0, resources: 0 };
    let tax = 0;
    let resources = 0;
    for (const op of operations) {
      if (op.nick.toLowerCase() !== myNickLower) continue;
      if (op.quantity <= 0) continue;
      if (isTaxOperation(op)) {
        tax += op.quantity;
      } else if (isTalentOperation(op)) {
        resources += op.quantity;
      }
    }
    return { tax, resources };
  }, [operations, myNick, myNickLower]);

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
          Персонаж «{myNick}» не найден в составе клана 2315. Если вы состоите в другом клане, этот раздел недоступен.
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
        {daysToDeadline >= 0 && daysToDeadline <= 15 && isPaymentDue && (
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
          </div>
        </div>
      )}

      {/* Ресурсы талантов по 3 группам */}
      {TALENT_RESOURCE_GROUPS.map((group) => {
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
