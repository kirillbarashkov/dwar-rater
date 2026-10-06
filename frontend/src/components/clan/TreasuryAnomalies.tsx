import { useCallback, useEffect, useState } from 'react';
import { getTreasuryAnomalies } from '../../api/clanInfo';
import type { TreasuryAnomaliesResponse } from '../../types/clanInfo';
import './TreasuryAnomalies.css';

interface TreasuryAnomaliesProps {
  clanId?: number;
  /** Clicking a ghost nick offers it to the history-transfer panel below. */
  onPickNick?: (nick: string) => void;
}

/**
 * «Диагностика казны» — what looks wrong in the stored operations.
 *
 * Read-only on purpose: it corrects nothing. A payment from a nick the roster no
 * longer knows and an amount above the norm are judgement calls the treasurer
 * reviews; the two marked «жёстко» (a future date, a negative amount) are
 * corruption, and those are refused on the way in, so no new ones can appear.
 */
export function TreasuryAnomalies({ clanId, onPickNick }: TreasuryAnomaliesProps) {
  const [data, setData] = useState<TreasuryAnomaliesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!clanId) return;
    setIsLoading(true);
    setError('');
    try {
      setData(await getTreasuryAnomalies(clanId));
    } catch {
      setError('Не удалось загрузить отчёт по аномалиям');
    } finally {
      setIsLoading(false);
    }
  }, [clanId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!clanId) return null;

  return (
    <section className="an-panel">
      <div className="an-header">
        <h3 className="an-title">
          Диагностика казны
          {data && (
            <span className="an-muted">
              проверено операций: {data.checked.operations}, участников: {data.checked.members}
            </span>
          )}
        </h3>
        <button className="an-btn" onClick={() => void load()} disabled={isLoading}>
          {isLoading ? 'Проверяю…' : 'Проверить снова'}
        </button>
      </div>

      {error && <div className="an-error">{error}</div>}

      {isLoading && !data ? (
        <div className="an-muted">Загрузка…</div>
      ) : !data || data.total === 0 ? (
        <div className="an-clean">
          Ничего подозрительного не найдено: суммы положительные, дат из будущего нет,
          платежи сделаны участниками состава.
        </div>
      ) : (
        <>
          <div className="an-summary">
            Найдено {data.total} подозрительн
            {data.total === 1 ? 'ая запись' : 'ых записей'} в {data.items.length} категориях
          </div>
          {data.items.map((item) => (
            <div key={item.code} className={`an-group ${item.blocking ? 'an-group-blocking' : ''}`}>
              <div className="an-group-header">
                <span className="an-group-label">{item.label}</span>
                <span className="an-count">{item.count}</span>
                {item.blocking && (
                  <span className="an-badge-blocking" title="Такие записи отклоняются при импорте и правке">
                    жёстко
                  </span>
                )}
              </div>
              <table className="an-table">
                <tbody>
                  {item.examples.map((row, idx) => (
                    <tr key={`${item.code}-${row.id ?? idx}`}>
                      <td className="an-date">{row.date || '—'}</td>
                      <td className="an-nick">{row.nick || '—'}</td>
                      <td className="an-num">{row.quantity ?? '—'}</td>
                      <td className="an-note">{row.note || ''}</td>
                      <td className="an-action">
                        {/* The remedy sits next to the diagnosis: a ghost nick is
                            usually a rename, and the transfer is right below. */}
                        {item.code === 'unknown_nick' && row.nick && onPickNick && (
                          <button className="an-pick" onClick={() => onPickNick(row.nick as string)}>
                            перенести историю
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {item.count > item.examples.length && (
                <div className="an-muted">…и ещё {item.count - item.examples.length}</div>
              )}
            </div>
          ))}
        </>
      )}

      <p className="an-note-footer">
        Отчёт ничего не меняет. «Жёсткие» записи (будущая дата, отрицательная сумма)
        отклоняются при импорте и правке — то есть новые такие не появятся.
      </p>
    </section>
  );
}
