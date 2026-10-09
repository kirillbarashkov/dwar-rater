import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  applyBulkCompensation,
  getTaxLedger,
  previewBulkCompensation,
} from '../../api/clanInfo';
import type { BulkCompensationPlan } from '../../types/clanInfo';
import { MONTHS_RU } from '../../utils/treasury';
import './BulkCompensationPanel.css';

interface BulkCompensationPanelProps {
  clanId?: number;
  /** The clan roster — who can be waived at all. */
  members?: Array<{ nick: string; level?: number }>;
  /** treasury:write — without it the panel renders nothing. */
  canManage?: boolean;
}

/**
 * «Массовый зачёт»: waive the tax of several members for a month in one go.
 *
 * The selectable list is the ROSTER, not the ledger: when a clan has no treasury
 * operations at all the ledger answers `no_operations` with zero rows, and a
 * treasurer still has to be able to waive someone. The ledger is only a hint — it
 * says who actually owes for the month, and those come pre-selected.
 *
 * Nothing is written until the preview has been shown and confirmed, and the
 * preview runs the very same planner the write does, so it cannot promise
 * something different from what gets applied.
 */
export function BulkCompensationPanel({
  clanId,
  members = [],
  canManage = false,
}: BulkCompensationPanelProps) {
  const now = new Date();
  const [month, setMonth] = useState<number>(now.getMonth() + 1);
  const [year, setYear] = useState<number>(now.getFullYear());
  // nick (lower-cased) -> the month's {debt, paid} from the ledger.
  const [debts, setDebts] = useState<Record<string, { debt: number; paid: number }>>({});
  const [ledgerEmpty, setLedgerEmpty] = useState(false);
  // A clan roster is dozens of nicks, so the list filters instead of dumping.
  const [filter, setFilter] = useState<'debtors' | 'all'>('debtors');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [comment, setComment] = useState('');
  const [plan, setPlan] = useState<BulkCompensationPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const loadDebts = useCallback(async () => {
    if (!clanId) return;
    setIsLoading(true);
    setError('');
    try {
      const ledger = await getTaxLedger(clanId, {
        from_month: month,
        from_year: year,
        to_month: month,
        to_year: year,
      });
      const rows = ledger.rows || [];
      // A one-month window: the row's own debt IS that month's debt, and this is
      // the same chain the «Сальдо» tab renders. Keys are lower-cased because the
      // ledger and the roster may spell a nick differently.
      const map: Record<string, { debt: number; paid: number }> = {};
      for (const row of rows) {
        map[row.nick.toLowerCase()] = { debt: row.debt, paid: row.paid_total };
      }
      setDebts(map);
      setLedgerEmpty(rows.length === 0);
      setPlan(null);
      setNotice('');
      // The usual errand is "waive the debtors", so they come pre-selected.
      setSelected(
        members
          .filter((member) => (map[member.nick.toLowerCase()]?.debt || 0) > 0)
          .map((member) => member.nick)
      );
    } catch {
      setError('Не удалось получить данные лицевого счёта');
    } finally {
      setIsLoading(false);
    }
  }, [clanId, month, year, members]);

  useEffect(() => {
    void loadDebts();
  }, [loadDebts]);

  // Debtors first — that is the list the treasurer came for.
  const roster = useMemo(
    () =>
      members
        .map((member) => {
          const cell = debts[member.nick.toLowerCase()];
          return {
            nick: member.nick,
            debt: cell?.debt || 0,
            paid: cell?.paid || 0,
          };
        })
        .sort((a, b) => b.debt - a.debt || a.nick.localeCompare(b.nick)),
    [members, debts]
  );

  const debtors = useMemo(() => roster.filter((row) => row.debt > 0), [roster]);

  // Plain substring, case-insensitive: «сын» should find «Сын_Дракона».
  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    const base = filter === 'debtors' ? debtors : roster;
    return query ? base.filter((row) => row.nick.toLowerCase().includes(query)) : base;
  }, [roster, debtors, filter, search]);

  const payload = useMemo(
    () => ({ nicks: selected, months: [month], year, comment }),
    [selected, month, year, comment]
  );

  const toggle = (nick: string) =>
    setSelected((prev) => (prev.includes(nick) ? prev.filter((n) => n !== nick) : [...prev, nick]));

  const handlePreview = async () => {
    if (!clanId || selected.length === 0) return;
    setIsLoading(true);
    setError('');
    setNotice('');
    try {
      setPlan(await previewBulkCompensation(clanId, payload));
    } catch {
      setError('Не удалось построить предпросмотр');
    } finally {
      setIsLoading(false);
    }
  };

  const handleApply = async () => {
    if (!clanId || !plan) return;
    setIsApplying(true);
    setError('');
    try {
      const result = await applyBulkCompensation(clanId, payload);
      // Reload first, THEN announce: loadDebts() clears the notice and the plan,
      // so announcing before it would wipe the confirmation the treasurer needs.
      await loadDebts();
      setPlan(result.plan);
      setNotice(
        `Засчитано ${result.created} из ${result.plan.totals.pairs} — остальное пропущено или заблокировано`
      );
    } catch {
      setError('Не удалось применить зачёт');
    } finally {
      setIsApplying(false);
    }
  };

  if (!clanId || !canManage) return null;

  const blocked = plan?.items.filter((item) => item.action === 'blocked') ?? [];

  return (
    <section className="bc-panel">
      <div className="bc-header">
        <h3 className="bc-title">Массовый зачёт налога</h3>
        <div className="bc-period">
          <select
            className="bc-select"
            value={month}
            onChange={(event) => setMonth(Number(event.target.value))}
          >
            {MONTHS_RU.map((name, index) => (
              <option key={name} value={index + 1}>
                {name}
              </option>
            ))}
          </select>
          <input
            className="bc-year"
            type="number"
            value={year}
            onChange={(event) => setYear(Number(event.target.value))}
          />
        </div>
      </div>

      {error && <div className="bc-error">{error}</div>}
      {notice && <div className="bc-notice">{notice}</div>}

      <div className="bc-debtors">
        {roster.length === 0 ? (
          <div className="bc-muted">Состав клана не загружен.</div>
        ) : (
          <>
            <div className="bc-debtors-head">
              <span className="bc-muted">
                Участников: {roster.length} · с долгом: {debtors.length}
              </span>
              <button
                className="bc-link"
                onClick={() => setSelected(debtors.map((row) => row.nick))}
                disabled={debtors.length === 0}
              >
                выбрать должников
              </button>
              <button className="bc-link" onClick={() => setSelected([])}>
                снять выбор
              </button>
            </div>
            <div className="bc-filters">
              <button
                className={`bc-chip ${filter === 'debtors' ? 'bc-chip-on' : ''}`}
                onClick={() => setFilter('debtors')}
              >
                Должники ({debtors.length})
              </button>
              <button
                className={`bc-chip ${filter === 'all' ? 'bc-chip-on' : ''}`}
                onClick={() => setFilter('all')}
              >
                Все ({roster.length})
              </button>
              <input
                className="bc-search"
                placeholder="поиск по нику"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <span className="bc-muted">выбрано: {selected.length}</span>
            </div>
            {ledgerEmpty && (
              <div className="bc-muted bc-hint">
                В казне нет операций за этот месяц — выбирай вручную.
              </div>
            )}
            <div className="bc-list">
              {visible.length === 0 ? (
                <div className="bc-muted">Никого не найдено.</div>
              ) : (
                visible.map((row) => (
                  <label key={row.nick} className="bc-item">
                    <input
                      type="checkbox"
                      checked={selected.includes(row.nick)}
                      onChange={() => toggle(row.nick)}
                    />
                    <span className="bc-nick">{row.nick}</span>
                    {row.debt > 0 ? (
                      <span className="bc-debt">
                        долг {row.debt}
                        {row.paid > 0 ? ` · оплачено ${row.paid}` : ''}
                      </span>
                    ) : (
                      row.paid > 0 && <span className="bc-paid">оплачено {row.paid}</span>
                    )}
                  </label>
                ))
              )}
            </div>
          </>
        )}
      </div>

      <input
        className="bc-comment"
        placeholder="Комментарий (виден в журнале)"
        value={comment}
        onChange={(event) => setComment(event.target.value)}
      />

      <div className="bc-actions">
        <button
          className="bc-btn"
          onClick={() => void handlePreview()}
          disabled={isLoading || selected.length === 0}
        >
          {isLoading ? 'Считаю…' : `Предпросмотр (${selected.length})`}
        </button>
        <button
          className="bc-btn bc-btn-primary"
          onClick={() => void handleApply()}
          disabled={isApplying || !plan || plan.totals.create === 0}
        >
          {isApplying ? 'Применяю…' : plan ? `Применить (${plan.totals.create})` : 'Применить'}
        </button>
      </div>

      {plan && (
        <>
          <div className="bc-totals">
            Будет создано: <b>{plan.totals.create}</b> · пропущено: {plan.totals.skip} ·
            заблокировано: {plan.totals.blocked}
          </div>
          <table className="bc-table">
            <thead>
              <tr>
                <th>Ник</th>
                <th>Месяц</th>
                <th>Сумма</th>
                <th>Что будет</th>
              </tr>
            </thead>
            <tbody>
              {plan.items.map((item, index) => (
                <tr key={`${item.nick}-${item.month}-${index}`} className={`bc-row-${item.action}`}>
                  <td>{item.nick}</td>
                  <td>
                    {item.month}.{item.year}
                  </td>
                  <td className="bc-num">{item.amount}</td>
                  <td>
                    {item.action === 'create'
                      ? 'зачтём'
                      : item.action === 'skip'
                        ? item.reason
                          ? plan.labels[item.reason]
                          : 'пропуск'
                        : plan.labels[item.reason || ''] || 'нельзя'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {blocked.length > 0 && (
            <p className="bc-note">
              Заблокированные — это не отказ по существу: закрытый месяц править нельзя, а месяц,
              который ещё не начался, ждёт своего времени.
            </p>
          )}
        </>
      )}
    </section>
  );
}
