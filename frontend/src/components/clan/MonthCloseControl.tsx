import { useCallback, useEffect, useRef, useState } from 'react';
import {
  closeTreasuryMonth,
  getTreasuryMonths,
  reopenTreasuryMonth,
} from '../../api/clanInfo';
import { MONTHS_RU } from '../../utils/treasury';

interface MonthCloseControlProps {
  clanId?: number;
  month: number;
  year: number;
  /** treasury:approve — closing a month is a decision, not a read. */
  canApprove: boolean;
  onChanged: (isClosed: boolean) => void;
}

/**
 * «Закрытие месяца»: the treasurer freezes a settled month.
 *
 * A closed month stops accepting manual writes and bulk imports, so the money
 * already reported for it cannot be re-shaken retroactively. Both the close and
 * the reopen are audited and the reopen puts everything back, which is why this
 * asks for a confirmation instead of a modal wizard.
 */
export function MonthCloseControl({
  clanId,
  month,
  year,
  canApprove,
  onChanged,
}: MonthCloseControlProps) {
  const [isClosed, setIsClosed] = useState(false);
  const [note, setNote] = useState('');
  // null = idle, otherwise which change is awaiting a confirmation click.
  const [pending, setPending] = useState<'close' | 'reopen' | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  // Held in a ref so the parent can pass an inline callback without making the
  // fetch effect re-run on every render (which would loop).
  const onChangedRef = useRef(onChanged);
  useEffect(() => {
    onChangedRef.current = onChanged;
  }, [onChanged]);

  const load = useCallback(async () => {
    if (!clanId) return;
    try {
      const data = await getTreasuryMonths(clanId);
      const found = data.months.find((m) => m.month === month && m.year === year);
      setIsClosed(Boolean(found));
      setNote(found?.note ?? '');
      onChangedRef.current(Boolean(found));
    } catch {
      // A read failure must not block the tab: the backend still refuses writes.
      setIsClosed(false);
    }
  }, [clanId, month, year]);

  useEffect(() => {
    void load();
    setPending(null);
  }, [load]);

  if (!canApprove) {
    return isClosed ? <span className="mc-badge">🔒 месяц закрыт</span> : null;
  }

  const run = async (action: 'close' | 'reopen') => {
    if (!clanId) return;
    setIsSaving(true);
    setError('');
    try {
      if (action === 'close') {
        await closeTreasuryMonth(clanId, year, month, note);
      } else {
        await reopenTreasuryMonth(clanId, year, month);
      }
      setPending(null);
      await load();
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })?.response
        ?.data?.message;
      setError(message || 'Не удалось изменить состояние месяца');
    } finally {
      setIsSaving(false);
    }
  };

  const label = `${MONTHS_RU[month]} ${year}`;

  if (pending) {
    const closing = pending === 'close';
    return (
      <span className="mc-control">
        <span className="mc-question">
          {closing
            ? `Закрыть ${label}? Правки и импорт за этот месяц начнут отклоняться.`
            : `Переоткрыть ${label}? Месяц снова примет правки и импорт.`}
        </span>
        <button
          className="mc-btn mc-btn-confirm"
          onClick={() => void run(pending)}
          disabled={isSaving}
        >
          {closing ? 'Да, закрыть' : 'Да, переоткрыть'}
        </button>
        <button className="mc-btn" onClick={() => setPending(null)} disabled={isSaving}>
          Отмена
        </button>
        {error && <span className="mc-error">{error}</span>}
      </span>
    );
  }

  return (
    <span className="mc-control">
      {isClosed ? (
        <>
          <span className="mc-badge" title={note || undefined}>
            🔒 месяц закрыт
          </span>
          <button
            className="mc-btn"
            onClick={() => setPending('reopen')}
            disabled={isSaving}
            title="Снова разрешить правки и импорт за этот месяц"
          >
            Переоткрыть
          </button>
        </>
      ) : (
        <>
          <input
            className="mc-input"
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Пометка (необязательно)"
            maxLength={200}
          />
          <button
            className="mc-btn"
            onClick={() => setPending('close')}
            disabled={isSaving}
            title="Зафиксировать месяц: правки и импорт за него будут отклоняться"
          >
            Закрыть месяц
          </button>
        </>
      )}
      {error && <span className="mc-error">{error}</span>}
    </span>
  );
}
