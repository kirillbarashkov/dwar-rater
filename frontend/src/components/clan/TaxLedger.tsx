import { Fragment, useCallback, useEffect, useState } from 'react';
import { getTaxLedger } from '../../api/clanInfo';
import type { TaxLedgerResponse, TaxLedgerRow } from '../../types/clanInfo';
import { MONTHS_RU } from '../../utils/treasury';
import './TaxLedger.css';

interface TaxLedgerProps {
  clanId: number;
  /** Период раздела задаёт, по какой месяц смотрим («До»). */
  month: number;
  year: number;
}

const monthOptions = Array.from({ length: 12 }, (_, i) => i + 1);

function money(value: number): string {
  return value.toLocaleString('ru-RU');
}

function signed(value: number): string {
  return `${value > 0 ? '+' : ''}${money(value)}`;
}

export function TaxLedger({ clanId, month: periodMonth, year: periodYear }: TaxLedgerProps) {
  const now = new Date();
  const [fromMonth, setFromMonth] = useState(1);
  const [fromYear, setFromYear] = useState(periodYear);
  const [toMonth, setToMonth] = useState(periodMonth);
  const [toYear, setToYear] = useState(periodYear);
  const [data, setData] = useState<TaxLedgerResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [onlyDebtors, setOnlyDebtors] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const periodValid =
    fromYear * 12 + fromMonth <= toYear * 12 + toMonth && fromYear >= 2000;

  const load = useCallback(async () => {
    if (!periodValid) {
      setError('Начало периода позже его конца');
      return;
    }
    setIsLoading(true);
    setError('');
    try {
      setData(
        await getTaxLedger(clanId, {
          from_month: fromMonth,
          from_year: fromYear,
          to_month: toMonth,
          to_year: toYear,
        })
      );
    } catch {
      setError('Не удалось загрузить лицевой счёт');
    } finally {
      setIsLoading(false);
    }
  }, [clanId, fromMonth, fromYear, toMonth, toYear, periodValid]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows: TaxLedgerRow[] = data?.rows ?? [];
  const visible = onlyDebtors ? rows.filter((r) => r.debt > 0) : rows;
  const debtorCount = rows.filter((r) => r.debt > 0).length;

  const copy = async () => {
    const header = ['Ник', 'Ур.', 'Начислено', 'Оплачено', 'Зачёты', 'Перенос из пред.', 'К переносу', 'Долг', 'Сальдо'];
    const lines = visible.map((r) => [
      r.nick,
      r.level,
      r.norm_total,
      r.paid_total,
      r.compensation_total,
      r.carried_in_total,
      r.carried_out_final,
      r.debt,
      r.balance,
    ]);
    await navigator.clipboard.writeText(
      [header, ...lines].map((line) => line.join('\t')).join('\n')
    );
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <section className="tl-panel">
      <div className="tl-header">
        <h3 className="tl-title">
          Лицевой счёт участников
          {rows.length > 0 && (
            <span className="tl-muted">
              {rows.length} чел., должников {debtorCount}
            </span>
          )}
        </h3>
        <div className="tl-actions">
          <label className="tl-field">
            От
            <select
              className="tl-select"
              value={fromMonth}
              onChange={(e) => setFromMonth(Number(e.target.value))}
            >
              {monthOptions.map((m) => (
                <option key={m} value={m}>
                  {MONTHS_RU[m]}
                </option>
              ))}
            </select>
            <input
              className="tl-input"
              type="number"
              value={fromYear}
              min={2000}
              onChange={(e) => setFromYear(Number(e.target.value))}
            />
          </label>
          <label className="tl-field">
            До
            <select
              className="tl-select"
              value={toMonth}
              onChange={(e) => setToMonth(Number(e.target.value))}
            >
              {monthOptions.map((m) => (
                <option key={m} value={m}>
                  {MONTHS_RU[m]}
                </option>
              ))}
            </select>
            <input
              className="tl-input"
              type="number"
              value={toYear}
              min={2000}
              onChange={(e) => setToYear(Number(e.target.value))}
            />
          </label>
          <button
            className="tl-btn"
            onClick={() => {
              setFromMonth(1);
              setFromYear(now.getFullYear());
              setToMonth(now.getMonth() + 1);
              setToYear(now.getFullYear());
            }}
            title="С начала текущего года до текущего месяца"
          >
            Текущий год
          </button>
          <button
            className="tl-btn"
            onClick={() => {
              setFromMonth(1);
              setFromYear(now.getFullYear() - 1);
              setToMonth(12);
              setToYear(now.getFullYear() - 1);
            }}
            title="Январь — декабрь прошлого года"
          >
            Прошлый год
          </button>
          <label className="tl-check" title="Скрыть тех, у кого долга нет">
            <input
              type="checkbox"
              checked={onlyDebtors}
              onChange={(e) => setOnlyDebtors(e.target.checked)}
            />
            только должники
          </label>
          <button className="tl-btn" onClick={() => void copy()} disabled={!visible.length}>
            {copied ? '✓ Скопировано' : 'Копировать'}
          </button>
        </div>
      </div>

      {error && <div className="tl-error">{error}</div>}

      {isLoading ? (
        <div className="tl-muted">Загрузка…</div>
      ) : !rows.length ? (
        <div className="tl-empty">
          За выбранный период операций нет. Расширь период или проверь, что казна
          импортирована за эти месяцы.
        </div>
      ) : (
        <div className="tl-table-wrap">
          <table className="tl-table">
            <thead>
              <tr>
                <th>Ник</th>
                <th className="tl-num">Ур.</th>
                <th className="tl-num">Начислено</th>
                <th className="tl-num">Оплачено</th>
                <th className="tl-num" title="Зачтённая переплата — не деньги, а закрытие месяца">
                  Зачёты
                </th>
                <th className="tl-num" title="Переплата, перенесённая из прошлого месяца">
                  Перенос из пред.
                </th>
                <th className="tl-num" title="Переплата, переносимая за конец периода">
                  К переносу
                </th>
                <th className="tl-num">Долг</th>
                <th className="tl-num">Сальдо</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <Fragment key={row.nick}>
                  <tr
                    className="tl-row"
                    onClick={() =>
                      setExpanded(expanded === row.nick ? null : row.nick)
                    }
                  >
                    <td className="tl-nick">
                      <span className="tl-caret">{expanded === row.nick ? '▾' : '▸'}</span>
                      {row.nick}
                    </td>
                    <td className="tl-num">{row.level}</td>
                    <td className="tl-num">{money(row.norm_total)}</td>
                    <td className="tl-num">{money(row.paid_total)}</td>
                    <td className="tl-num">{row.compensation_total ? money(row.compensation_total) : '—'}</td>
                    <td className="tl-num">{row.carried_in_total ? money(row.carried_in_total) : '—'}</td>
                    <td className="tl-num tl-credit">{row.carried_out_final ? money(row.carried_out_final) : '—'}</td>
                    <td className={`tl-num ${row.debt ? 'tl-debt' : ''}`}>
                      {row.debt ? money(row.debt) : '—'}
                    </td>
                    <td className={`tl-num tl-balance ${row.balance > 0 ? 'tl-credit' : ''} ${row.balance < 0 ? 'tl-debt' : ''}`}>
                      {signed(row.balance)}
                    </td>
                  </tr>
                  {expanded === row.nick && (
                    <tr key={`${row.nick}-months`} className="tl-months-row">
                      <td colSpan={9}>
                        <table className="tl-months">
                          <thead>
                            <tr>
                              <th>Месяц</th>
                              <th className="tl-num">Норма</th>
                              <th className="tl-num">Оплачено</th>
                              <th className="tl-num">Зачёт</th>
                              <th className="tl-num">Перенос из пред.</th>
                              <th className="tl-num">К переносу</th>
                              <th className="tl-num">Долг</th>
                            </tr>
                          </thead>
                          <tbody>
                            {row.months.map((cell) => (
                              <tr key={`${cell.year}-${cell.month}`}>
                                <td>{MONTHS_RU[cell.month]} {cell.year}</td>
                                <td className="tl-num">{money(cell.norm)}</td>
                                <td className="tl-num">{money(cell.paid)}</td>
                                <td className="tl-num">{cell.compensation ? money(cell.compensation) : '—'}</td>
                                <td className="tl-num">{cell.carried_in ? money(cell.carried_in) : '—'}</td>
                                <td className="tl-num tl-credit">{cell.carried_out ? money(cell.carried_out) : '—'}</td>
                                <td className={`tl-num ${cell.debt ? 'tl-debt' : ''}`}>
                                  {cell.debt ? money(cell.debt) : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
            <tfoot>
              <tr className="tl-totals">
                <td>Итого ({visible.length})</td>
                <td />
                <td className="tl-num">{money(data?.totals.norm_total ?? 0)}</td>
                <td className="tl-num">{money(data?.totals.paid_total ?? 0)}</td>
                <td className="tl-num">{money(data?.totals.compensation_total ?? 0)}</td>
                <td className="tl-num">{money(data?.totals.carried_in_total ?? 0)}</td>
                <td className="tl-num tl-credit">{money(data?.totals.carried_out_final ?? 0)}</td>
                <td className="tl-num tl-debt">{money(data?.totals.debt ?? 0)}</td>
                <td className="tl-num">{signed(data?.totals.balance ?? 0)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      <p className="tl-note">
        Сальдо = переплата к переносу минус долг. Считается той же цепочкой месяцев,
        что и предложения переноса, поэтому сумма здесь всегда совпадает с тем, что
        казначей видит на вкладке «Налоги». Зачёты — не деньги: они закрывают месяц,
        но переплаты не создают.
      </p>
    </section>
  );
}