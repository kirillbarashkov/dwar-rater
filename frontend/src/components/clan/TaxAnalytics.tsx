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

  const renderStatusBadge = (summary: PlayerTaxSummary) => {
    if (summary.status === 'future_member') {
      const monthLabel = summary.paymentStartMonth ? MONTHS_RU[summary.paymentStartMonth.month] : '';
      return <span className="tax-badge tax-badge-future">Оплата с {monthLabel}</span>;
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
              <span className="tax-kpi-value">{filteredPlayers.length}</span>
              <span className="tax-kpi-label">Показано</span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{monthSummary.expectedTotal.toLocaleString()}</span>
              <span className="tax-kpi-label">Ожидалось</span>
            </div>
            <div className="tax-kpi-card">
              <span className="tax-kpi-value">{compensatedPlayers.length}</span>
              <span className="tax-kpi-label">Зачтено</span>
            </div>
            <div className="tax-kpi-card tax-kpi-danger">
              <span className="tax-kpi-value">{notPaidPlayers.length}</span>
              <span className="tax-kpi-label">Не заплатил</span>
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
              <h3 className="tax-section-title">Сводная — {periodLabel}</h3>
              {filteredPlayers.length > 0 ? (
                <table className="tax-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Игрок</th>
                      <th>Уровень</th>
                      <th>Уплачено</th>
                      <th>Норма</th>
                      <th>Статус</th>
                      <th>Компенсация</th>
                      <th>Комментарий</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPlayers.map((p, idx) => (
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
              ) : (
                <div className="tax-empty">Нет данных за период</div>
              )}
            </section>

            <section className="tax-section">
              <h3 className="tax-section-title">
                <span className="tax-status-dot tax-status-notpaid" />
                Не заплатил ({notPaidPlayers.length})
              </h3>
              {notPaidPlayers.length > 0 ? (
                <table className="tax-table">
                  <thead>
                    <tr>
                      <th>Игрок</th>
                      <th>Уровень</th>
                      <th>Норма</th>
                    </tr>
                  </thead>
                  <tbody>
                    {notPaidPlayers.map(p => (
                      <tr key={p.nick}>
                        <td className="tax-nick">{p.nick}</td>
                        <td>{p.playerLevel ?? '-'}</td>
                        <td className="tax-debt">{p.normAmount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="tax-empty">Нет должников</div>
              )}
            </section>

            {compensatedPlayers.length > 0 && (
              <section className="tax-section">
                <h3 className="tax-section-title">
                  <span className="tax-status-dot tax-status-compensated" />
                  Зачтено ({compensatedPlayers.length})
                </h3>
                <table className="tax-table">
                  <thead>
                    <tr>
                      <th>Игрок</th>
                      <th>Уровень</th>
                      <th>Сумма</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compensatedPlayers.map(p => (
                      <tr key={p.nick}>
                        <td className="tax-nick">{p.nick}</td>
                        <td>{p.playerLevel ?? '-'}</td>
                        <td className="tax-paid">{p.normAmount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}

            {paidDelayedPlayers.length > 0 && (
              <section className="tax-section">
                <h3 className="tax-section-title">
                  <span className="tax-status-dot tax-status-delayed" />
                  Заплатил + Задержано ({paidDelayedPlayers.length})
                </h3>
                <table className="tax-table">
                  <thead>
                    <tr>
                      <th>Игрок</th>
                      <th>Уровень</th>
                      <th>Уплачено</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paidDelayedPlayers.map(p => (
                      <tr key={p.nick}>
                        <td className="tax-nick">{p.nick}</td>
                        <td>{p.playerLevel ?? '-'}</td>
                        <td className="tax-paid">{p.totalPaid}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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