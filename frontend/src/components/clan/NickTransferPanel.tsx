import { useEffect, useState } from 'react';
import { applyNickTransfer, previewNickTransfer } from '../../api/clanInfo';
import type { NickTransferPlan, ReasonCode } from '../../types/clanInfo';
import './NickTransferPanel.css';

interface NickTransferPanelProps {
  clanId?: number;
  /** Reason codes served by the API. */
  reasonCodes?: ReasonCode[];
  /** treasury:write — without it the panel renders nothing. */
  canManage?: boolean;
  /** Prefilled by a click on a finding in the report above. */
  fromNick?: string;
}

/**
 * «Перенос истории ника»: reconnect a renamed character's history.
 *
 * An in-game rename leaves the old nick holding the payments and level records
 * while the new one starts from zero — the ledger then shows a ghost and a debtor
 * for the same person. The transfer moves operations, carry-over rows and level
 * events; nothing is deleted and no amounts are merged (a carry-over the receiving
 * nick already has for that month is reported, not summed).
 *
 * «Проверить» runs the same planner the transfer does, so the review cannot
 * promise something different from what gets written.
 */
export function NickTransferPanel({
  clanId,
  reasonCodes = [],
  canManage = false,
  fromNick = '',
}: NickTransferPanelProps) {
  const [source, setSource] = useState(fromNick);
  const [target, setTarget] = useState('');
  const [reason, setReason] = useState('renamed_nick');
  const [plan, setPlan] = useState<NickTransferPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (fromNick) {
      setSource(fromNick);
      setPlan(null);
      setNotice('');
      setError('');
    }
  }, [fromNick]);

  const reasonOptions =
    reasonCodes.length > 0 ? reasonCodes : [{ code: 'renamed_nick', label: 'Переименование в игре' }];

  const ready = source.trim() !== '' && target !== '' && reason !== '';

  const handlePreview = async () => {
    if (!clanId || !ready) return;
    setIsLoading(true);
    setError('');
    setNotice('');
    try {
      const result = await previewNickTransfer(clanId, {
        from_nick: source.trim(),
        to_nick: target,
        reason,
      });
      setPlan(result.plan);
    } catch (err: unknown) {
      setPlan(null);
      setError(describeError(err, 'Не удалось проверить перенос'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleApply = async () => {
    if (!clanId || !plan || plan.is_empty) return;
    setIsApplying(true);
    setError('');
    try {
      const result = await applyNickTransfer(clanId, {
        from_nick: source.trim(),
        to_nick: target,
        reason,
      });
      setNotice(
        `Перенесено: оплат ${result.operations}, переносов ${result.carryovers}, ` +
          `событий уровня ${result.level_events}` +
          (result.skipped_carryovers.length > 0
            ? ` · не перенесено переносов: ${result.skipped_carryovers.length}`
            : '')
      );
      setPlan(null);
    } catch (err: unknown) {
      setError(describeError(err, 'Не удалось выполнить перенос'));
    } finally {
      setIsApplying(false);
    }
  };

  if (!clanId || !canManage) return null;

  return (
    <section className="nt-panel">
      <h3 className="nt-title">Перенос истории ника (переименование)</h3>

      {error && <div className="nt-error">{error}</div>}
      {notice && <div className="nt-notice">{notice}</div>}

      <div className="nt-form">
        <label className="nt-field">
          <span className="nt-label">Старый ник</span>
          <input
            className="nt-input"
            value={source}
            placeholder="ник, которого нет в составе"
            onChange={(event) => {
              setSource(event.target.value);
              setPlan(null);
            }}
          />
        </label>
        <label className="nt-field">
          <span className="nt-label">Новый ник (из состава)</span>
          {/* Free text on purpose: the server looks the nick up case-insensitively
              and stores the roster spelling, so a typo cannot create a twin nick.*/}
          <input
            className="nt-input"
            value={target}
            placeholder="новый ник игрока"
            onChange={(event) => {
              setTarget(event.target.value);
              setPlan(null);
            }}
          />
        </label>
        <label className="nt-field">
          <span className="nt-label">Причина</span>
          <select
            className="nt-input"
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
              setPlan(null);
            }}
          >
            {reasonOptions.map((code) => (
              <option key={code.code} value={code.code}>
                {code.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="nt-actions">
        <button className="nt-btn" onClick={() => void handlePreview()} disabled={isLoading || !ready}>
          {isLoading ? 'Считаю…' : 'Проверить'}
        </button>
        <button
          className="nt-btn nt-btn-primary"
          onClick={() => void handleApply()}
          disabled={isApplying || !plan || plan.is_empty}
        >
          {isApplying ? 'Переношу…' : 'Перенести'}
        </button>
      </div>

      {plan && (
        <div className="nt-plan">
          {plan.is_empty ? (
            <div className="nt-muted">
              У «{plan.from_nick}» нет истории для переноса — проверьте ник.
            </div>
          ) : (
            <>
              <div className="nt-summary">
                Перейдёт от <b>{plan.from_nick}</b> к <b>{plan.to_nick}</b>: оплат{' '}
                <b>{plan.operations.count}</b> на сумму {plan.operations.total_quantity}
                {plan.level_events.count > 0 && <> · событий уровня {plan.level_events.count}</>}
                {plan.carryovers.move.length > 0 && <> · переносов {plan.carryovers.move.length}</>}
              </div>
              {plan.operations.first_date && (
                <div className="nt-muted">
                  Период: {plan.operations.first_date} — {plan.operations.last_date}; месяцев:{' '}
                  {plan.operations.months.length}
                </div>
              )}
              {plan.carryovers.skipped_count > 0 && (
                <div className="nt-warn">
                  Не переносится переносов: {plan.carryovers.skipped_count} — у получателя уже есть
                  перенос за этот месяц. Суммы не складываются: решите вручную.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

function describeError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { error?: string; message?: string } } })?.response
    ?.data;
  if (detail) return detail.message || detail.error || fallback;
  return fallback;
}
