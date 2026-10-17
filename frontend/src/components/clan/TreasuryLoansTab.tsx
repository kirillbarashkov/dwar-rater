import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTreasuryLoans } from '../../api/treasuryLoans';
import type {
  LoanOperation,
  LoanPerson,
  TreasuryLoansResponse,
} from '../../types/treasuryLoans';
import './TreasuryLoansTab.css';

// Почему заём открыт. Подписи приходят с бэкенда, а объяснения живут здесь: казначей
// должен понимать, что делать с суммой, а не только видеть её.
const REASON_HINTS: Record<string, string> = {
  none: 'Пары нет: автоматика не нашла рядом по дате вторую операцию этого человека.',
  candidate: 'Пара ждёт решения казначея: пока решения нет, взятое числится за человеком.',
  rejected: 'Пара отклонена казначеем — значит, возврат по ней не признали.',
  split: 'Пара разорвана: эта сторона вернулась в учёт, вторая списана на таланты клана.',
};

const formatNumber = (value: number) => value.toLocaleString('ru-RU');

export function TreasuryLoansTab({ clanId }: { clanId: number }) {
  const navigate = useNavigate();
  const [data, setData] = useState<TreasuryLoansResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [ops, setOps] = useState<LoanOperation[]>([]);
  const [opsLoading, setOpsLoading] = useState(false);
  // Номер запроса: ответ по прошлому человеку не должен подменить список текущего.
  const requestId = useRef(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await getTreasuryLoans(clanId));
    } catch {
      setError('Не удалось загрузить займы');
    } finally {
      setLoading(false);
    }
  }, [clanId]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (person: LoanPerson) => {
    if (expanded === person.nick) {
      setExpanded(null);
      setOps([]);
      return;
    }
    setExpanded(person.nick);
    setOps([]);
    setOpsLoading(true);
    const id = ++requestId.current;
    try {
      const result = await getTreasuryLoans(clanId, person.nick);
      if (requestId.current === id) {
        setOps(result.ops ?? []);
      }
    } catch {
      if (requestId.current === id) {
        setError('Не удалось загрузить операции участника');
      }
    } finally {
      if (requestId.current === id) {
        setOpsLoading(false);
      }
    }
  };

  const reasonBadge = (reason: string, count?: number) => (
    <span
      key={reason}
      className={`ln-reason ln-reason-${reason}`}
      title={REASON_HINTS[reason] ?? reason}
    >
      {data?.reason_labels[reason] ?? reason}
      {count !== undefined && `: ${count}`}
    </span>
  );

  if (loading) {
    return <div className="ln-loading">Загрузка займов…</div>;
  }

  return (
    <div className="ln-tab">
      <div className="treasury-header">
        <div className="treasury-header-top">
          <h2
            className="treasury-title"
            title="Участники, взявшие из казны и не вернувшие"
          >
            Займы из казны
          </h2>
        </div>
        <p className="ln-hint">
          Это не «долг» из «Статуса персонажа» — там недосдача налога, другое понятие.
          Здесь взятое из казны, по которому нет подтверждённой пары. Закрывает заём
          подтверждение пары или списание на таланты клана.
        </p>
      </div>

      {error && <div className="ln-error">{error}</div>}

      {data && (
        <>
          <div className="ln-totals">
            <span title="Сколько участников числится в списке">
              Людей: <b>{formatNumber(data.totals.people)}</b>
            </span>
            <span title="Сколько минусовых операций не закрыто">
              Операций: <b>{formatNumber(data.totals.ops)}</b>
            </span>
            <span title="Сколько всего взято из казны и не возвращено">
              Взято: <b>{formatNumber(data.totals.taken)}</b>
            </span>
            {data.totals.excluded_hidden > 0 && (
              <span
                className="ln-totals-muted"
                title="Эти минусовые операции скрыты правилами групп исключений: объект выведен из отчётов"
              >
                скрыто правилами групп: {formatNumber(data.totals.excluded_hidden)}
              </span>
            )}
          </div>

          {data.people.length === 0 ? (
            <div className="treasury-empty">
              Открытых займов нет: за всеми минусовыми операциями стоят подтверждённые
              пары или списания на таланты.
            </div>
          ) : (
            <div className="ln-list">
              <div className="ln-row ln-row-head">
                <span>Участник</span>
                <span>Операций</span>
                <span>Взято</span>
                <span>Период</span>
                <span>Почему открыто</span>
              </div>

              {data.people.map((person) => (
                <div key={person.nick} className="ln-item">
                  <button
                    type="button"
                    className={`ln-row ln-row-body ${
                      expanded === person.nick ? 'ln-row-open' : ''
                    }`}
                    onClick={() => toggle(person)}
                    title="Показать операции этого участника"
                  >
                    <span className="ln-nick">{person.nick}</span>
                    <span>{formatNumber(person.count)}</span>
                    <span className="ln-taken">{formatNumber(person.taken)}</span>
                    <span className="ln-dates">
                      {person.first_date === person.last_date
                        ? person.first_date
                        : `${person.first_date} — ${person.last_date}`}
                    </span>
                    <span className="ln-reasons">
                      {Object.entries(person.reasons).map(([reason, count]) =>
                        reasonBadge(reason, count),
                      )}
                    </span>
                  </button>

                  {expanded === person.nick && (
                    <div className="ln-ops">
                      {opsLoading ? (
                        <div className="ln-ops-note">Загрузка операций…</div>
                      ) : ops.length === 0 ? (
                        <div className="ln-ops-note">Операций нет</div>
                      ) : (
                        ops.map((op) => (
                          <div key={op.id} className="ln-op">
                            <span className="ln-op-date">{op.date}</span>
                            <span className="ln-op-type">{op.operation_type}</span>
                            <span className="ln-op-object">{op.object_name}</span>
                            <span className="ln-op-qty">
                              −{formatNumber(op.taken)}
                            </span>
                            {reasonBadge(op.reason)}
                            {op.pair_id && (
                              <button
                                type="button"
                                className="ln-op-link"
                                title="Открыть эту пару в «Обменах и долгах»"
                                onClick={() =>
                                  navigate(
                                    `/clan/${clanId}?tab=treasury-pairs&pair=${op.pair_id}`,
                                  )
                                }
                              >
                                К паре
                              </button>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
