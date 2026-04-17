import { useMemo } from 'react';
import type { TreasuryOperationData } from '../../types/clanInfo';
import { parseDate, formatDateKey } from '../../utils/treasury';
import { isTaxOperation, isTalentOperation } from '../../utils/treasury';
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
import './MiscAnalytics.css';

interface MiscAnalyticsProps {
  operations: TreasuryOperationData[];
}

const CHART_COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

interface OperationTypeStat {
  name: string;
  value: number;
  income: number;
  expense: number;
}

interface DayStat {
  date: string;
  count: number;
  income: number;
  expense: number;
}

export function MiscAnalytics({ operations }: MiscAnalyticsProps) {
  const miscOperations = useMemo(() => {
    return operations.filter(op => {
      if (isTaxOperation(op)) return false;
      if (isTalentOperation(op)) return false;
      return true;
    });
  }, [operations]);

  const operationsByType = useMemo((): OperationTypeStat[] => {
    const byType: Record<string, { value: number; income: number; expense: number }> = {};

    for (const op of miscOperations) {
      if (!byType[op.operation_type]) {
        byType[op.operation_type] = { value: 0, income: 0, expense: 0 };
      }
      byType[op.operation_type].value += 1;
      if (op.quantity > 0) {
        byType[op.operation_type].income += op.quantity;
      } else {
        byType[op.operation_type].expense += Math.abs(op.quantity);
      }
    }

    return Object.values(byType)
      .map(data => ({
        name: Object.keys(byType).find(k => byType[k] === data)!,
        ...data,
      }))
      .sort((a, b) => b.value - a.value);
  }, [miscOperations]);

  const operationsByDay = useMemo((): DayStat[] => {
    const byDay: Record<string, DayStat> = {};

    for (const op of miscOperations) {
      const parsed = parseDate(op.date);
      if (!parsed) continue;
      const key = formatDateKey(parsed.day, parsed.month, parsed.year);

      if (!byDay[key]) {
        byDay[key] = { date: key, count: 0, income: 0, expense: 0 };
      }
      byDay[key].count += 1;
      if (op.quantity > 0) {
        byDay[key].income += op.quantity;
      } else {
        byDay[key].expense += Math.abs(op.quantity);
      }
    }

    return Object.values(byDay)
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-30);
  }, [miscOperations]);

  const playerActivity = useMemo(() => {
    const byPlayer: Record<string, { count: number; income: number; expense: number }> = {};

    for (const op of miscOperations) {
      if (!byPlayer[op.nick]) {
        byPlayer[op.nick] = { count: 0, income: 0, expense: 0 };
      }
      byPlayer[op.nick].count += 1;
      if (op.quantity > 0) {
        byPlayer[op.nick].income += op.quantity;
      } else {
        byPlayer[op.nick].expense += Math.abs(op.quantity);
      }
    }

    return Object.entries(byPlayer)
      .map(([nick, data]) => ({ nick, ...data }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 15);
  }, [miscOperations]);

  const topObjects = useMemo(() => {
    const byObject: Record<string, number> = {};
    for (const op of miscOperations) {
      byObject[op.object_name] = (byObject[op.object_name] || 0) + 1;
    }
    return Object.entries(byObject)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [miscOperations]);

  const totalIncome = miscOperations.filter(op => op.quantity > 0).reduce((sum, op) => sum + op.quantity, 0);
  const totalExpense = miscOperations.filter(op => op.quantity < 0).reduce((sum, op) => sum + Math.abs(op.quantity), 0);
  const uniquePlayers = new Set(miscOperations.map(op => op.nick)).size;

  return (
    <div className="misc-analytics">
      <header className="misc-header">
        <h2 className="misc-title">Прочие операции</h2>
      </header>

      <div className="misc-kpi">
        <div className="misc-kpi-card">
          <span className="misc-kpi-value">{miscOperations.length}</span>
          <span className="misc-kpi-label">Операций</span>
        </div>
        <div className="misc-kpi-card">
          <span className="misc-kpi-value">+{totalIncome.toLocaleString()}</span>
          <span className="misc-kpi-label">Приход</span>
        </div>
        <div className="misc-kpi-card">
          <span className="misc-kpi-value">-{totalExpense.toLocaleString()}</span>
          <span className="misc-kpi-label">Расход</span>
        </div>
        <div className="misc-kpi-card">
          <span className="misc-kpi-value">{uniquePlayers}</span>
          <span className="misc-kpi-label">Игроков</span>
        </div>
      </div>

      <div className="misc-grid">
        <section className="misc-chart-card">
          <h3 className="misc-section-title">Операции по дням</h3>
          {operationsByDay.length > 0 ? (
            <div className="misc-chart-container">
              <ResponsiveContainer width="100%" height={200}>
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
                  />
                  <Legend />
                  <Bar dataKey="income" name="Приход" fill="#22c55e" stackId="a" />
                  <Bar dataKey="expense" name="Расход" fill="#ef4444" stackId="a" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="misc-empty">Нет данных</div>
          )}
        </section>

        <section className="misc-chart-card">
          <h3 className="misc-section-title">По типам операций</h3>
          {operationsByType.length > 0 ? (
            <div className="misc-chart-container">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={operationsByType}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
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
            <div className="misc-empty">Нет данных</div>
          )}
        </section>

        <section className="misc-section">
          <h3 className="misc-section-title">Активность игроков</h3>
          {playerActivity.length > 0 ? (
            <table className="misc-table">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Операций</th>
                  <th>Приход</th>
                  <th>Расход</th>
                </tr>
              </thead>
              <tbody>
                {playerActivity.map((p, idx) => (
                  <tr key={p.nick}>
                    <td className="misc-nick">{idx + 1}. {p.nick}</td>
                    <td>{p.count}</td>
                    <td className="misc-income">+{p.income}</td>
                    <td className="misc-expense">-{p.expense}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="misc-empty">Нет данных</div>
          )}
        </section>

        <section className="misc-section">
          <h3 className="misc-section-title">Популярные объекты</h3>
          {topObjects.length > 0 ? (
            <table className="misc-table">
              <thead>
                <tr>
                  <th>Объект</th>
                  <th>Операций</th>
                </tr>
              </thead>
              <tbody>
                {topObjects.map(o => (
                  <tr key={o.name}>
                    <td className="misc-object">{o.name}</td>
                    <td>{o.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="misc-empty">Нет данных</div>
          )}
        </section>

        <section className="misc-section misc-section-wide">
          <h3 className="misc-section-title">Детализация по типам</h3>
          {operationsByType.length > 0 ? (
            <table className="misc-table">
              <thead>
                <tr>
                  <th>Тип</th>
                  <th>Операций</th>
                  <th>Приход</th>
                  <th>Расход</th>
                </tr>
              </thead>
              <tbody>
                {operationsByType.map(t => (
                  <tr key={t.name}>
                    <td className="misc-type">{t.name}</td>
                    <td>{t.value}</td>
                    <td className="misc-income">+{t.income.toLocaleString()}</td>
                    <td className="misc-expense">-{t.expense.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="misc-empty">Нет данных</div>
          )}
        </section>
      </div>
    </div>
  );
}