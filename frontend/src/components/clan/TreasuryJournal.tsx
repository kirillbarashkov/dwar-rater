import { useCallback, useEffect, useState } from 'react';
import type { ReasonCode, TreasuryJournalEntry } from '../../types/clanInfo';
import { getTreasuryJournal, revertTreasuryJournalEntry } from '../../api/clanInfo';
import './TreasuryJournal.css';

interface TreasuryJournalProps {
  clanId: number;
  /** treasury:write — may write a reversing entry. */
  canManage: boolean;
  /** Reason codes come from the API so the dropdown cannot drift from the stored values. */
  reasonCodes: ReasonCode[];
}

const ACTION_LABELS: Record<string, string> = {
  treasury_operation_update: 'Правка операции',
  treasury_journal_revert: 'Откат правки',
  treasury_compensation_create: 'Зачёт',
  treasury_import: 'Импорт казны',
  treasury_backup_restore: 'Восстановление бэкапа',
  tax_carryover_recompute: 'Пересчёт переносов',
  tax_carryover_confirmed: 'Перенос подтверждён',
  tax_carryover_cancelled: 'Перенос отменён',
  tax_carryover_bulk_confirm: 'Переносы подтверждены',
  tax_carryover_bulk_cancel: 'Переносы отменены',
};

/** Reasons the backend writes itself (not part of the treasurer's code list). */
const SYSTEM_REASONS: Record<string, string> = { revert: 'Откат' };

function fmtFlag(value: boolean | undefined): string {
  return value ? 'да' : 'нет';
}

function describeChange(entry: TreasuryJournalEntry): string {
  const o = entry.old ?? {};
  const n = entry.new ?? {};
  if (entry.action === 'treasury_operation_update' || entry.action === 'treasury_journal_revert') {
    const parts: string[] = [];
    if (o.quantity !== n.quantity) parts.push(`кол-во ${o.quantity ?? '—'} → ${n.quantity ?? '—'}`);
    if (o.compensation_flag !== n.compensation_flag) {
      parts.push(`зачёт ${fmtFlag(o.compensation_flag)} → ${fmtFlag(n.compensation_flag)}`);
    }
    if ((o.compensation_comment ?? '') !== (n.compensation_comment ?? '')) {
      parts.push(`коммент. «${o.compensation_comment || '—'}» → «${n.compensation_comment || '—'}»`);
    }
    return parts.join('; ') || '—';
  }
  if (entry.action === 'treasury_import') {
    return `добавлено ${n.imported ?? 0}, обновлено ${n.updated ?? 0}, пропущено ${n.skipped ?? 0}`;
  }
  if (entry.action === 'treasury_backup_restore') {
    return `${n.filename ?? 'бэкап'}: операций ${n.imported ?? 0}`;
  }
  if (entry.action === 'treasury_compensation_create') {
    const months = Array.isArray(n.months) ? n.months.join(', ') : '';
    return `${n.nick ?? ''} — норма ${n.norm_amount ?? 0}, месяцы ${months}`;
  }
  if (entry.action.startsWith('tax_carryover')) {
    const who = n.nick ? `${n.nick}: ` : '';
    const amount = n.amount !== undefined ? String(n.amount) : '';
    const status = n.status ? ` → ${n.status}` : '';
    const period = n.month ? ` (${n.month}.${n.year})` : '';
    return `${who}${amount}${status}${period}`.trim() || '—';
  }
  return '—';
}

function formatWhen(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('ru-RU');
}

export function TreasuryJournal({ clanId, canManage, reasonCodes }: TreasuryJournalProps) {
  const [entries, setEntries] = useState<TreasuryJournalEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [actionFilter, setActionFilter] = useState('');
  const [nickFilter, setNickFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getTreasuryJournal(clanId, {
        limit: 100,
        action: actionFilter || undefined,
        nick: nickFilter || undefined,
      });
      setEntries(data.entries);
      setTotal(data.total);
    } catch {
      setEntries([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [clanId, actionFilter, nickFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleRevert = async (entry: TreasuryJournalEntry) => {
    setIsSaving(true);
    setStatus(null);
    try {
      const result = await revertTreasuryJournalEntry(clanId, entry.id);
      setStatus(
        `Откат применён: операция №${result.operation_id} восстановлена (кол-во ${
          String(result.restored?.quantity ?? '—')
        })`
      );
      await load();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setStatus(detail || 'Откат не применён — см. консоль');
      console.error('Journal revert failed:', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="tj-panel">
      <div className="tj-header">
        <h3 className="tj-title">
          Журнал корректировок
          <span className="tj-change">записей: {total}</span>
        </h3>
        <div className="tj-actions">
          {status && <span className="tj-status">{status}</span>}
          <button className="tj-btn" onClick={() => void load()} disabled={isLoading || isSaving}>
            ⟳ Обновить
          </button>
        </div>
      </div>

      <div className="tj-note">
        Кто и когда правил казну. Откат пишет обратную запись и не удаляет историю; он
        отказывается работать, если операцию меняли после этой правки.
      </div>

      <div className="tj-filters">
        <select
          className="tj-select"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        >
          <option value="">Все действия</option>
          {Object.entries(ACTION_LABELS).map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
        <input
          className="tj-input"
          type="text"
          placeholder="Фильтр по нику"
          value={nickFilter}
          onChange={(e) => setNickFilter(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="tj-empty">Загрузка…</div>
      ) : entries.length === 0 ? (
        <div className="tj-empty">Записей нет</div>
      ) : (
        <div className="tj-table-wrapper">
          <table className="tj-table">
            <thead>
              <tr>
                <th>Когда</th>
                <th>Кто</th>
                <th>Действие</th>
                <th>Игрок</th>
                <th>Что изменилось</th>
                <th>Причина</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="tj-when">{formatWhen(entry.created_at)}</td>
                  <td className="tj-who">{entry.username}</td>
                  <td>{ACTION_LABELS[entry.action] ?? entry.action}</td>
                  <td className="tj-nick">{entry.nick ?? '—'}</td>
                  <td className="tj-change">{describeChange(entry)}</td>
                  <td>
                    {entry.reason ? (
                      <span className="tj-reason">
                        {reasonCodes.find((r) => r.code === entry.reason)?.label ??
                          SYSTEM_REASONS[entry.reason] ??
                          entry.reason}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    {entry.revertable && canManage && (
                      <button
                        className="tj-btn"
                        onClick={() => void handleRevert(entry)}
                        disabled={isSaving}
                        title="Восстановить прежние значения (обратной записью)"
                      >
                        ↶ Откатить
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
