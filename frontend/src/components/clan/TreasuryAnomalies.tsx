import { useCallback, useEffect, useState } from 'react';
import {
  getTreasuryAnomalies,
  muteTreasuryAnomaly,
  unmuteTreasuryAnomaly,
} from '../../api/clanInfo';
import type { TreasuryAnomaliesResponse } from '../../types/clanInfo';
import './TreasuryAnomalies.css';

// Fallback labels, mirroring the backend's LABELS: a muted category has no item in
// the response, so its friendly name cannot come from there.
const FALLBACK_LABELS: Record<string, string> = {
  future_date: 'Дата в будущем',
  negative_quantity: 'Отрицательная сумма',
  before_join: 'Платёж раньше вступления',
  unknown_nick: 'Ник не из состава',
  above_norm: 'Сумма заметно выше нормы',
};

interface TreasuryAnomaliesProps {
  clanId?: number;
  /** treasury:write — muting a finding is a decision, not a read. */
  canManage?: boolean;
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
export function TreasuryAnomalies({
  clanId,
  canManage = false,
  onPickNick,
}: TreasuryAnomaliesProps) {
  const [data, setData] = useState<TreasuryAnomaliesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isMuting, setIsMuting] = useState(false);

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

  // «Это нормально»: the decision is stored per clan, so the next treasurer opening
  // the report does not have to make it again.
  const setMute = async (code: string, ref: string, on: boolean) => {
    if (!clanId) return;
    setIsMuting(true);
    setError('');
    try {
      if (on) {
        await muteTreasuryAnomaly(clanId, { code, ref });
      } else {
        await unmuteTreasuryAnomaly(clanId, { code, ref });
      }
      await load();
    } catch {
      setError('Не удалось изменить пометку');
    } finally {
      setIsMuting(false);
    }
  };

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
                {canManage && (
                  <button
                    className="an-pick"
                    onClick={() => void setMute(item.code, '', true)}
                    disabled={isMuting}
                    title="Больше не показывать эту категорию целиком"
                  >
                    это нормально
                  </button>
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
                        {canManage && !item.blocking && row.nick && (
                          <button
                            className="an-pick"
                            onClick={() => void setMute(item.code, row.nick as string, true)}
                            disabled={isMuting}
                            title={`Больше не показывать ${row.nick} в этой категории`}
                          >
                            нормально
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

      {data && data.muted.length > 0 && (
        <div className="an-muted-list">
          <span className="an-muted">Скрыто по решению казначея: {data.muted.length}</span>
          {data.muted.map((mute) => (
            <button
              key={`${mute.code}-${mute.ref}`}
              className="an-pick"
              onClick={() => void setMute(mute.code, mute.ref, false)}
              disabled={isMuting}
              title="Вернуть в отчёт"
            >
              ↺ {FALLBACK_LABELS[mute.code] || mute.code}
              {mute.ref ? ` / ${mute.ref}` : ''}
            </button>
          ))}
        </div>
      )}

      <p className="an-note-footer">
        Отчёт ничего не меняет. «Жёсткие» записи (будущая дата, отрицательная сумма)
        отклоняются при импорте и правке — то есть новые такие не появятся.
      </p>
    </section>
  );
}
