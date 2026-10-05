import { useState } from 'react';
import type { TaxCarryoverMonth } from '../../types/clanInfo';
import { MONTHS_RU } from '../../utils/treasury';
import './TaxCarryoverPanel.css';

interface TaxCarryoverPanelProps {
  month: number;
  year: number;
  data: TaxCarryoverMonth | null;
  /** treasury:approve — confirm/cancel/recompute. */
  canApprove: boolean;
  isSaving: boolean;
  onRecompute: () => void;
  onReview: (id: number, action: 'confirm' | 'cancel', comment?: string) => void;
  onBulk: (ids: number[], action: 'confirm' | 'cancel') => void;
}

const STATUS_LABELS: Record<string, string> = {
  pending: '⏳ ждёт решения',
  confirmed: '✓ перенесено',
  cancelled: '✕ отменено',
};

export function TaxCarryoverPanel({
  month,
  year,
  data,
  canApprove,
  isSaving,
  onRecompute,
  onReview,
  onBulk,
}: TaxCarryoverPanelProps) {
  const [comment, setComment] = useState('');

  if (!data) return null;

  const period = `${MONTHS_RU[month]} ${year}`;
  const pending = data.carryovers.filter((c) => c.status === 'pending');
  const reviewed = data.carryovers.filter((c) => c.status !== 'pending');

  return (
    <section className={`tc-panel ${pending.length > 0 ? 'tc-panel-attention' : ''}`}>
      <div className="tc-header">
        <h3 className="tc-title">
          Переплата налога — перенос из {period}
          {pending.length > 0 && (
            <span className="tc-badge tc-badge-pending">{pending.length} ждёт решения</span>
          )}
          {pending.length > 0 && (
            <span className="tc-muted">к переносу {data.pending_total.toLocaleString('ru-RU')}</span>
          )}
        </h3>
        <div className="tc-actions">
          {canApprove && data.is_closed && (
            <button
              className="tc-btn"
              onClick={onRecompute}
              disabled={isSaving}
              title="Пересчитать предложения по текущим данным казны"
            >
              ⟳ Пересчитать
            </button>
          )}
          {canApprove && pending.length > 0 && (
            <>
              <button
                className="tc-btn tc-btn-ok"
                onClick={() => onBulk(pending.map((c) => c.id), 'confirm')}
                disabled={isSaving}
              >
                Подтвердить все ({pending.length})
              </button>
              <button
                className="tc-btn tc-btn-no"
                onClick={() => onBulk(pending.map((c) => c.id), 'cancel')}
                disabled={isSaving}
              >
                Отменить все ({pending.length})
              </button>
            </>
          )}
        </div>
      </div>

      {!data.is_closed && (
        <div className="tc-note">
          Месяц ещё не завершён — это прогноз. Перенос станет доступен для подтверждения после
          закрытия месяца.
        </div>
      )}

      {pending.length > 0 && (
        <>
          <div className="tc-table-wrapper">
            <table className="tc-table">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Переплата</th>
                  <th>Статус</th>
                  <th>Решение</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((c) => (
                  <tr key={c.id}>
                    <td className="tc-nick">{c.nick}</td>
                    <td className="tc-amount">{c.amount.toLocaleString('ru-RU')}</td>
                    <td>
                      <span className="tc-badge tc-badge-pending">{STATUS_LABELS.pending}</span>
                    </td>
                    <td className="tc-decision">
                      {canApprove ? (
                        <>
                          <button
                            className="tc-icon-btn tc-icon-ok"
                            onClick={() => onReview(c.id, 'confirm', comment)}
                            disabled={isSaving}
                            title="Перенести на следующий месяц"
                          >
                            ✓ Подтвердить
                          </button>
                          <button
                            className="tc-icon-btn tc-icon-no"
                            onClick={() => onReview(c.id, 'cancel', comment)}
                            disabled={isSaving}
                            title="Не переносить"
                          >
                            ✕ Отменить
                          </button>
                        </>
                      ) : (
                        <span className="tc-muted">решение принимает казначей</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {canApprove && (
            <input
              className="tc-comment"
              type="text"
              placeholder="Комментарий к решению (необязательно)"
              value={comment}
              maxLength={500}
              onChange={(e) => setComment(e.target.value)}
            />
          )}
        </>
      )}

      {data.is_closed && pending.length === 0 && (
        <div className="tc-empty">
          Переплат к переносу за {period} нет
          {reviewed.length > 0 ? ' — все решения приняты.' : '.'}
        </div>
      )}

      {!data.is_closed &&
        (data.preview.length > 0 ? (
          <div className="tc-table-wrapper">
            <table className="tc-table">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Предварительно к переносу</th>
                </tr>
              </thead>
              <tbody>
                {data.preview.map((p) => (
                  <tr key={p.nick}>
                    <td className="tc-nick">{p.nick}</td>
                    <td className="tc-amount">{p.amount.toLocaleString('ru-RU')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="tc-empty">По текущим данным переплаты нет.</div>
        ))}

      {reviewed.length > 0 && (
        <details className="tc-history">
          <summary>История решений за {period} ({reviewed.length})</summary>
          <table className="tc-table">
            <thead>
              <tr>
                <th>Игрок</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Комментарий</th>
              </tr>
            </thead>
            <tbody>
              {reviewed.map((c) => (
                <tr key={c.id}>
                  <td className="tc-nick">{c.nick}</td>
                  <td className="tc-amount">{c.amount.toLocaleString('ru-RU')}</td>
                  <td>
                    <span
                      className={`tc-badge ${c.status === 'confirmed' ? 'tc-badge-ok' : 'tc-badge-no'}`}
                    >
                      {STATUS_LABELS[c.status]}
                    </span>
                  </td>
                  <td className="tc-comment-cell" title={c.comment || undefined}>
                    {c.comment || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </section>
  );
}
