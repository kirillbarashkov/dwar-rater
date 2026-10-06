import { useState } from 'react';
import { reassignTreasuryOperation } from '../../api/clanInfo';

interface ReassignButtonProps {
  /** Optional, like everywhere in this tab: absent clan means no action. */
  clanId?: number;
  /** The member's latest payment row; a member without one has nothing to move. */
  operationId?: number;
  nick: string;
  members: Array<{ nick: string }>;
  reasonCodes: Array<{ code: string; label: string }>;
  disabled?: boolean;
  onDone: () => void;
}

/**
 * «Перераспределить» — the payment was credited to the wrong member.
 *
 * Money itself is not edited here: the row keeps its amount, date and type and
 * only changes owner, which is why the tax analytics of both members move at
 * once and the treasury journal records the reason. The target list is the
 * clan roster — the backend refuses a nick the clan never had.
 */
export function ReassignButton({
  clanId,
  operationId,
  nick,
  members,
  reasonCodes,
  disabled,
  onDone,
}: ReassignButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [target, setTarget] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  if (!operationId || !clanId) return null;

  if (!isOpen) {
    return (
      <button
        className="tax-edit-btn"
        onClick={() => {
          setIsOpen(true);
          setTarget('');
          setReason('');
          setError('');
        }}
        disabled={disabled}
        title="Перераспределить: платёж принадлежит другому участнику"
      >
        →
      </button>
    );
  }

  const save = async () => {
    setIsSaving(true);
    setError('');
    try {
      await reassignTreasuryOperation(clanId, operationId, {
        to_nick: target,
        reason,
      });
      setIsOpen(false);
      onDone();
    } catch (err) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data
        ?.error;
      setError(message || 'Не удалось перераспределить');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <span className="tax-actions">
      <select
        className="tax-edit-input"
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        title={`Сейчас платёж зачислен: ${nick}`}
      >
        <option value="">Кому…</option>
        {members
          .filter((m) => m.nick !== nick)
          .map((m) => (
            <option key={m.nick} value={m.nick}>
              {m.nick}
            </option>
          ))}
      </select>
      <select
        className="tax-edit-input tax-edit-reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        title="Причина — попадёт в журнал корректировок"
      >
        <option value="">Причина…</option>
        {reasonCodes.map((r) => (
          <option key={r.code} value={r.code}>
            {r.label}
          </option>
        ))}
      </select>
      <button
        className="tax-save-btn"
        onClick={() => void save()}
        disabled={!target || !reason || isSaving}
        title="Перенести платёж другому участнику"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </button>
      <button
        className="tax-cancel-btn"
        onClick={() => setIsOpen(false)}
        disabled={isSaving}
        title="Отмена"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
      {error && <span className="tax-reassign-error">{error}</span>}
    </span>
  );
}
