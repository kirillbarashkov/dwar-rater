import { useState, useEffect, useMemo, useCallback } from 'react';
import { getTreasuryOperations } from '../../api/clanInfo';
import type { TreasuryOperationData } from '../../types/clanInfo';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import {
  parseDate,
  formatDateKey,
  MONTHS_RU,
  PERIOD_OPTIONS,
  type PeriodType,
} from '../../utils/treasury';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import './TreasuryAnalytics.css';

interface TreasuryAnalyticsProps {
  clanId: number;
}

const CHART_COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

const INITIAL_FILTERS = {
  period: 'all' as PeriodType,
  rangeStart: '',
  rangeEnd: '',
  playerFilter: '',
  typeFilter: '',
};

interface KpiCard {
  label: string;
  value: string | number;
  subValue?: string;
  trend?: 'up' | 'down' | 'neutral';
  color?: string;
}

export function TreasuryAnalytics({ clanId }: TreasuryAnalyticsProps) {
  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth() + 1);

  const loadOperations = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getTreasuryOperations(clanId);
      setOperations(data);
    } catch {
      setOperations([]);
    } finally {
      setIsLoading(false);
    }
  }, [clanId]);

  useEffect(() => {
    loadOperations();
  }, [loadOperations]);

  const handlePeriodChange = (value: PeriodType) => {
    setFilters((prev) => ({ ...prev, period: value }));
  };

  const filtered = useMemo(() => {
    let result = [...operations];

    const now = new Date();
    const today = formatDateKey(now.getDate(), now.getMonth() + 1, now.getFullYear());

    switch (filters.period) {
      case 'today':
        result = result.filter((op) => {
          const parsed = parseDate(op.date);
          if (!parsed) return false;
          return formatDateKey(parsed.day, parsed.month, parsed.year) === today;
        });
        break;
      case 'month':
        result = result.filter((op) => {
          const parsed = parseDate(op.date);
          if (!parsed) return false;
          return parsed.year === currentYear && parsed.month === currentMonth;
        });
        break;
      case 'range':
        if (filters.rangeStart) {
          const startParts = filters.rangeStart.split('-').map(Number);
          const startDate = new Date(startParts[0], startParts[1] - 1, startParts[2]);
          result = result.filter((op) => {
            const parsed = parseDate(op.date);
            if (!parsed) return false;
            const opDate = new Date(parsed.year, parsed.month - 1, parsed.day);
            return opDate >= startDate;
          });
        }
        if (filters.rangeEnd) {
          const endParts = filters.rangeEnd.split('-').map(Number);
          const endDate = new Date(endParts[0], endParts[1] - 1, endParts[2]);
          endDate.setHours(23, 59, 59);
          result = result.filter((op) => {
            const parsed = parseDate(op.date);
            if (!parsed) return false;
            const opDate = new Date(parsed.year, parsed.month - 1, parsed.day);
            return opDate <= endDate;
          });
        }
        break;
    }

    if (filters.playerFilter) {
      const playerLower = filters.playerFilter.toLowerCase();
      result = result.filter((op) => op.nick.toLowerCase().includes(playerLower));
    }

    if (filters.typeFilter) {
      result = result.filter((op) => op.operation_type === filters.typeFilter);
    }

    return result;
  }, [operations, filters, currentYear, currentMonth]);

  const uniqueTypes = useMemo(() => {
    const types = new Set(operations.map((op) => op.operation_type));
    return Array.from(types).sort();
  }, [operations]);

  const kpis = useMemo((): KpiCard[] => {
    const totalOps = filtered.length;
    const totalIncome = filtered.filter((op) => op.quantity > 0).reduce((sum, op) => sum + op.quantity, 0);
    const totalExpense = filtered.filter((op) => op.quantity < 0).reduce((sum, op) => sum + Math.abs(op.quantity), 0);
    const uniquePlayers = new Set(filtered.map((op) => op.nick)).size;

    return [
      { label: 'Всего операций', value: totalOps.toLocaleString(), color: '#3b82f6' },
      { label: 'Приход', value: `+${totalIncome.toLocaleString()}`, color: '#22c55e' },
      { label: 'Расход', value: `-${totalExpense.toLocaleString()}`, color: '#ef4444' },
      { label: 'Активных игроков', value: uniquePlayers, color: '#8b5cf6' },
    ];
  }, [filtered]);

  const operationsByDay = useMemo(() => {
    const byDay: Record<string, { date: string; income: number; expense: number; count: number }> = {};

    for (const op of filtered) {
      const parsed = parseDate(op.date);
      if (!parsed) continue;
      const key = formatDateKey(parsed.day, parsed.month, parsed.year);
      if (!byDay[key]) {
        byDay[key] = { date: key, income: 0, expense: 0, count: 0 };
      }
      if (op.quantity > 0) {
        byDay[key].income += op.quantity;
      } else {
        byDay[key].expense += Math.abs(op.quantity);
      }
      byDay[key].count += 1;
    }

    return Object.values(byDay)
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-30);
  }, [filtered]);

  const operationsByType = useMemo(() => {
    const byType: Record<string, { name: string; value: number; income: number; expense: number }> = {};

    for (const op of filtered) {
      if (!byType[op.operation_type]) {
        byType[op.operation_type] = { name: op.operation_type, value: 0, income: 0, expense: 0 };
      }
      byType[op.operation_type].value += 1;
      if (op.quantity > 0) {
        byType[op.operation_type].income += op.quantity;
      } else {
        byType[op.operation_type].expense += Math.abs(op.quantity);
      }
    }

    return Object.values(byType).sort((a, b) => b.value - a.value);
  }, [filtered]);

  const topPlayers = useMemo(() => {
    const byPlayer: Record<string, { nick: string; operations: number; income: number; expense: number }> = {};

    for (const op of filtered) {
      if (!byPlayer[op.nick]) {
        byPlayer[op.nick] = { nick: op.nick, operations: 0, income: 0, expense: 0 };
      }
      byPlayer[op.nick].operations += 1;
      if (op.quantity > 0) {
        byPlayer[op.nick].income += op.quantity;
      } else {
        byPlayer[op.nick].expense += Math.abs(op.quantity);
      }
    }

    return Object.values(byPlayer)
      .sort((a, b) => b.operations - a.operations)
      .slice(0, 10);
  }, [filtered]);

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="treasury-analytics">
      <header className="treasury-analytics-header">
        <h2 className="treasury-analytics-title">Аналитика казны</h2>
      </header>

      <section className="treasury-analytics-filters" aria-label="Фильтры">
        <div className="ta-filter-row">
          <div className="ta-filter-group">
            <label htmlFor="ta-period">Период:</label>
            <select
              id="ta-period"
              value={filters.period}
              onChange={(e) => handlePeriodChange(e.target.value as PeriodType)}
            >
              {PERIOD_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {filters.period === 'month' && (
            <div className="ta-month-nav">
              <button onClick={() => {
                if (currentMonth === 1) { setCurrentMonth(12); setCurrentYear(y => y - 1); }
                else { setCurrentMonth(m => m - 1); }
              }}>←</button>
              <span>{MONTHS_RU[currentMonth]} {currentYear}</span>
              <button onClick={() => {
                if (currentMonth === 12) { setCurrentMonth(1); setCurrentYear(y => y + 1); }
                else { setCurrentMonth(m => m + 1); }
              }}>→</button>
            </div>
          )}

          {filters.period === 'range' && (
            <>
              <label className="ta-date-range">
                <span>От</span>
                <input
                  type="date"
                  value={filters.rangeStart}
                  onChange={(e) => setFilters((prev) => ({ ...prev, rangeStart: e.target.value }))}
                />
              </label>
              <span>—</span>
              <label className="ta-date-range">
                <span>До</span>
                <input
                  type="date"
                  value={filters.rangeEnd}
                  onChange={(e) => setFilters((prev) => ({ ...prev, rangeEnd: e.target.value }))}
                />
              </label>
            </>
          )}

          <div className="ta-filter-group">
            <input
              type="text"
              placeholder="Игрок..."
              value={filters.playerFilter}
              onChange={(e) => setFilters((prev) => ({ ...prev, playerFilter: e.target.value }))}
            />
          </div>

          <div className="ta-filter-group">
            <select
              value={filters.typeFilter}
              onChange={(e) => setFilters((prev) => ({ ...prev, typeFilter: e.target.value }))}
            >
              <option value="">Все типы</option>
              {uniqueTypes.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {(filters.playerFilter || filters.typeFilter || filters.rangeStart || filters.rangeEnd) && (
            <button
              className="ta-clear-filters"
              onClick={() => setFilters(INITIAL_FILTERS)}
              type="button"
            >
              ×
            </button>
          )}
        </div>
      </section>

      <section className="ta-kpi-grid" aria-label="Ключевые показатели">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="ta-kpi-card" style={{ '--kpi-color': kpi.color } as React.CSSProperties}>
            <span className="ta-kpi-value">{kpi.value}</span>
            <span className="ta-kpi-label">{kpi.label}</span>
          </div>
        ))}
      </section>

      <div className="ta-grid">
        <section className="ta-chart-card" aria-label="Операции по дням">
          <h3 className="ta-card-title">Операции по дням</h3>
          {operationsByDay.length > 0 ? (
            <div className="ta-chart-container">
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={operationsByDay} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border)',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                    labelStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Legend />
                  <Bar dataKey="income" name="Приход" fill="#22c55e" stackId="a" />
                  <Bar dataKey="expense" name="Расход" fill="#ef4444" stackId="a" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="ta-empty">Нет данных за выбранный период</div>
          )}
        </section>

        <section className="ta-chart-card" aria-label="Операции по типам">
          <h3 className="ta-card-title">Операции по типам</h3>
          {operationsByType.length > 0 ? (
            <div className="ta-chart-container">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={operationsByType}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    labelLine={false}
                  >
                    {operationsByType.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border)',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="ta-empty">Нет данных за выбранный период</div>
          )}
        </section>

        <section className="ta-card" aria-label="Топ игроков">
          <h3 className="ta-card-title">Топ игроков по операциям</h3>
          {topPlayers.length > 0 ? (
            <table className="ta-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Игрок</th>
                  <th>Операций</th>
                  <th>Приход</th>
                  <th>Расход</th>
                </tr>
              </thead>
              <tbody>
                {topPlayers.map((player, index) => (
                  <tr key={player.nick}>
                    <td className="ta-rank">{index + 1}</td>
                    <td className="ta-nick">{player.nick}</td>
                    <td>{player.operations}</td>
                    <td className="ta-income">+{player.income.toLocaleString()}</td>
                    <td className="ta-expense">-{player.expense.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="ta-empty">Нет данных за выбранный период</div>
          )}
        </section>

        <section className="ta-card" aria-label="Типы операций">
          <h3 className="ta-card-title">Детали по типам операций</h3>
          {operationsByType.length > 0 ? (
            <table className="ta-table">
              <thead>
                <tr>
                  <th>Тип</th>
                  <th>Операций</th>
                  <th>Приход</th>
                  <th>Расход</th>
                </tr>
              </thead>
              <tbody>
                {operationsByType.map((type) => (
                  <tr key={type.name}>
                    <td className="ta-type">{type.name}</td>
                    <td>{type.value}</td>
                    <td className="ta-income">+{type.income.toLocaleString()}</td>
                    <td className="ta-expense">-{type.expense.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="ta-empty">Нет данных за выбранный период</div>
          )}
        </section>
      </div>
    </div>
  );
}
