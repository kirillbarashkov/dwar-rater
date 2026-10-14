import { useCallback, useEffect, useState } from 'react';
import { getMemberStatus } from '../../api/memberStatus';
import type { MemberStatusResponse } from '../../types/memberStatus';
import './MemberStatusTab.css';

const KIND_LABELS: Record<string, string> = {
  exchange: 'Обмен',
  loan: 'Долг',
};

const STATUS_LABELS: Record<string, string> = {
  candidate: 'Ждёт решения',
  confirmed: 'Подтверждено',
  rejected: 'Отклонено',
};

const HINTS = {
  norm: 'Сколько монет участник должен сдать в этом месяце. Зависит от уровня персонажа.',
  paid: 'Сколько монет участник уже сдал в этом месяце. Зачёты сюда не входят.',
  compensation:
    'Зачёт — это не деньги, а книжная отметка: сумма закрыта другим способом. В сдачу не идёт.',
  carriedIn: 'Перенос: переплата с прошлых месяцев, которая закрывает часть нормы этого месяца.',
  debt: 'Открытый долг: сколько не хватает до нормы за этот месяц. Это реальный дефицит.',
  credit: 'Переплата: сдано больше нормы. Переносится на следующие месяцы.',
  balance: 'Сальдо: переплата минус долг. Плюс — участник в запасе, минус — должен клану.',
  resources: 'Ресурсы, сданные на склад в этом месяце. Обмены и долги сюда не попадают.',
  pairs: 'Обмены и долги участника: что на что менял. Подтверждённые операции не идут в налог и ресурсы.',
  history: 'Последние операции участника. Пометка «нейтральная» — операция отнесена к обмену или долгу.',
};

interface Props {
  clanId: number;
}

export function MemberStatusTab({ clanId }: Props) {
  const today = new Date();
  const [nick, setNick] = useState('');
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());
  const [data, setData] = useState<MemberStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!nick.trim()) {
      setData(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      setData(await getMemberStatus(clanId, nick.trim(), month, year));
    } catch {
      setError('Не удалось получить статус участника');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [clanId, nick, month, year]);

  useEffect(() => {
    load();
  }, [load]);

  const tax = data?.tax;

  return (
    <div className="member-status">
      <div className="treasury-header">
        <div className="treasury-header-top">
          <h2 className="treasury-title" title="Состояние дел участника в выбранном месяце">
            Статус персонажа
          </h2>
        </div>
        <div className="ta-filter-row">
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="ms-nick" title="Чей статус смотрим">
              Участник
            </label>
            <input
              id="ms-nick"
              className="ta-filter-input"
              value={nick}
              placeholder="ник полностью"
              onChange={(event) => setNick(event.target.value)}
            />
          </div>
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="ms-month" title="Месяц отчёта">
              Месяц
            </label>
            <select
              id="ms-month"
              className="ta-filter-input"
              value={month}
              onChange={(event) => setMonth(Number(event.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="ms-year" title="Год отчёта">
              Год
            </label>
            <input
              id="ms-year"
              className="ta-filter-input"
              type="number"
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
            />
          </div>
        </div>
      </div>

      {error && <div className="treasury-message treasury-message-error">{error}</div>}
      {loading && <div className="treasury-empty">Загружаю статус…</div>}
      {!loading && !nick.trim() && (
        <div className="treasury-empty">Введите ник участника, чтобы увидеть его состояние дел.</div>
      )}

      {!loading && tax && (
        <>
          <div className="ms-cards">
            <div className="ms-card" title={HINTS.norm}>
              <div className="ms-card-label">Норма</div>
              <div className="ms-card-value">{tax.norm}</div>
            </div>
            <div className="ms-card" title={HINTS.paid}>
              <div className="ms-card-label">Сдано</div>
              <div className="ms-card-value">{tax.paid}</div>
            </div>
            <div className="ms-card" title={HINTS.compensation}>
              <div className="ms-card-label">Зачёт</div>
              <div className="ms-card-value">{tax.compensation}</div>
            </div>
            <div className="ms-card" title={HINTS.carriedIn}>
              <div className="ms-card-label">Перенос</div>
              <div className="ms-card-value">{tax.carried_in}</div>
            </div>
            <div
              className={tax.debt > 0 ? 'ms-card ms-card-bad' : 'ms-card'}
              title={HINTS.debt}
            >
              <div className="ms-card-label">Долг</div>
              <div className="ms-card-value">{tax.debt}</div>
            </div>
            <div
              className={tax.credit > 0 ? 'ms-card ms-card-good' : 'ms-card'}
              title={HINTS.credit}
            >
              <div className="ms-card-label">Переплата</div>
              <div className="ms-card-value">{tax.credit}</div>
            </div>
            <div className="ms-card" title={HINTS.balance}>
              <div className="ms-card-label">Сальдо</div>
              <div className="ms-card-value">{tax.balance}</div>
            </div>
          </div>

          <h3 className="ms-section" title={HINTS.resources}>
            Ресурсы за месяц
          </h3>
          {data.resources.length === 0 ? (
            <div className="treasury-empty">Ресурсов за этот месяц нет.</div>
          ) : (
            <div className="ms-chips">
              {data.resources.map((item) => (
                <span key={`${item.operation_type}-${item.object_name}`} className="ms-chip">
                  {item.object_name} — {item.total}
                </span>
              ))}
            </div>
          )}

          <h3 className="ms-section" title={HINTS.pairs}>
            Обмены и долги
          </h3>
          {data.pairs.confirmed.length === 0 && data.pairs.candidates.length === 0 ? (
            <div className="treasury-empty">Обменов и долгов у участника нет.</div>
          ) : (
            <div className="ms-pairs">
              {[...data.pairs.candidates, ...data.pairs.confirmed].map((pair) => (
                <div key={pair.id} className="ms-pair">
                  <span
                    className={`tp-status tp-status-${pair.status}`}
                    title={pair.status === 'confirmed' ? HINTS.pairs : 'Кандидат: автоматика нашла похожие операции, решения ещё нет.'}
                  >
                    {STATUS_LABELS[pair.status] ?? pair.status}
                  </span>
                  <span className="tp-kind">{KIND_LABELS[pair.kind] ?? pair.kind}</span>
                  <span className="ms-pair-side">
                    {pair.first?.object_name ?? '—'} {pair.first?.quantity ?? ''}
                  </span>
                  <span className="tp-arrow">⇄</span>
                  <span className="ms-pair-side">
                    {pair.second?.object_name ?? '—'} {pair.second?.quantity ?? ''}
                  </span>
                </div>
              ))}
            </div>
          )}

          <h3 className="ms-section" title={HINTS.history}>
            История операций
          </h3>
          {data.history.length === 0 ? (
            <div className="treasury-empty">Операций у участника нет.</div>
          ) : (
            <div className="treasury-table-container">
              <table className="treasury-table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Тип</th>
                    <th>Объект</th>
                    <th>Кол-во</th>
                  </tr>
                </thead>
                <tbody>
                  {data.history.map((op) => (
                    <tr key={op.id}>
                      <td className="treasury-date">{op.date}</td>
                      <td className="treasury-type">
                        {op.operation_type}
                        {op.op_class === 'neutral' && (
                          <span className="treasury-neutral-flag" title={HINTS.history}>
                            нейтральная
                          </span>
                        )}
                      </td>
                      <td className="treasury-object">{op.object_name}</td>
                      <td
                        className={`treasury-quantity ${op.quantity >= 0 ? 'positive' : 'negative'}`}
                      >
                        {op.quantity > 0 ? `+${op.quantity}` : op.quantity}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
