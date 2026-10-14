import { useCallback, useEffect, useState } from 'react';
import {
  confirmTreasuryPair,
  getTreasuryPairs,
  rejectTreasuryPair,
  reviseTreasuryPair,
  unconfirmTreasuryPair,
} from '../../api/treasuryPairs';
import type { TreasuryPairData } from '../../types/treasuryPairs';
import './TreasuryPairsQueue.css';

const KIND_LABELS: Record<string, string> = {
  exchange: 'Обмен',
  loan: 'Долг',
};

const STATUS_LABELS: Record<string, string> = {
  candidate: 'Ждёт решения',
  confirmed: 'Подтверждено',
  rejected: 'Отклонено',
};

const STATUS_HINTS: Record<string, string> = {
  candidate:
    'Кандидат: автоматика нашла похожие операции, но казначей ещё не решил. Пока решения нет, операции учитываются как обычно.',
  confirmed:
    'Подтверждено: обе операции стали нейтральными и больше не идут в налог и ресурсы.',
  rejected:
    'Отклонено: это не обмен и не долг. Операции учитываются как обычно.',
};

const KIND_HINTS: Record<string, string> = {
  exchange: 'Обмен: участник отдал одно и получил другое — деньги на ресурсы или ресурсы на деньги.',
  loan: 'Долг: участник взял в долг или вернул долг. Учёт налога и ресурсов такой заём не меняет.',
};

const NEUTRAL_HINT =
  'Нейтральная операция: она не уменьшает и не увеличивает сдачу налога и ресурсов, потому что участвует в обмене или долге.';

interface Props {
  clanId: number;
}

export function TreasuryPairsQueue({ clanId }: Props) {
  const [pairs, setPairs] = useState<TreasuryPairData[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState('candidate');
  const [nick, setNick] = useState('');
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(
    null,
  );
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [pendingUnconfirm, setPendingUnconfirm] = useState<number | null>(null);
  const [reviseTarget, setReviseTarget] = useState<TreasuryPairData | null>(null);
  const [reviseKind, setReviseKind] = useState<'exchange' | 'loan'>('exchange');
  const [reviseComment, setReviseComment] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTreasuryPairs(clanId, {
        status: status || undefined,
        nick: nick.trim() || undefined,
        limit: 200,
      });
      setPairs(data.items);
      setTotal(data.total);
    } catch {
      setMessage({ type: 'error', text: 'Не удалось загрузить очередь пар' });
    } finally {
      setLoading(false);
    }
  }, [clanId, status, nick]);

  useEffect(() => {
    load();
  }, [load]);

  const handleConfirm = async (pair: TreasuryPairData, kind: 'exchange' | 'loan') => {
    try {
      await confirmTreasuryPair(clanId, pair.id, kind);
      setMessage({
        type: 'success',
        text: `Пара подтверждена как «${KIND_LABELS[kind]}». Обе операции стали нейтральными и больше не учитываются в налоге и ресурсах.`,
      });
      setConfirmingId(null);
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось подтвердить пару' });
    }
  };

  const handleReject = async (pair: TreasuryPairData) => {
    try {
      await rejectTreasuryPair(clanId, pair.id);
      setMessage({
        type: 'success',
        text: 'Пара отклонена. Операции учитываются как обычно.',
      });
      setConfirmingId(null);
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось отклонить пару' });
    }
  };

  const handleUnconfirm = async (pair: TreasuryPairData) => {
    try {
      await unconfirmTreasuryPair(clanId, pair.id);
      setMessage({
        type: 'success',
        text: 'Подтверждение отменено. Операции снова учитываются в налоге и ресурсах.',
      });
      setPendingUnconfirm(null);
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось отменить подтверждение' });
    }
  };

  const openRevise = (pair: TreasuryPairData) => {
    setReviseTarget(pair);
    setReviseKind(pair.kind === 'loan' ? 'loan' : 'exchange');
    setReviseComment('');
  };

  const handleRevise = async () => {
    if (!reviseTarget) return;
    try {
      await reviseTreasuryPair(clanId, reviseTarget.id, {
        kind: reviseKind,
        comment: reviseComment.trim(),
      });
      setMessage({
        type: 'success',
        text: 'Пара скорректирована. Изменение записано в историю.',
      });
      setReviseTarget(null);
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось скорректировать пару' });
    }
  };

  const renderSide = (pair: TreasuryPairData, which: 'first' | 'second') => {
    const side = which === 'first' ? pair.first : pair.second;
    if (!side) return <div className="tp-side tp-side-missing">Операция не найдена</div>;
    return (
      <div className="tp-side">
        <div className="tp-side-top">
          <span className="tp-side-nick">{side.nick}</span>
          <span className="tp-side-date">{side.date}</span>
        </div>
        <div className="tp-side-body">
          <span className="tp-side-type">{side.operation_type}</span>
          <span className="tp-side-object">{side.object_name}</span>
          <span
            className={side.quantity < 0 ? 'tp-side-qty tp-side-qty-out' : 'tp-side-qty tp-side-qty-in'}
          >
            {side.quantity > 0 ? `+${side.quantity}` : side.quantity}
          </span>
        </div>
        {side.op_class === 'neutral' && (
          <div className="tp-side-flag" title={NEUTRAL_HINT}>
            нейтральная
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="treasury-pairs">
      <div className="treasury-header">
        <div className="treasury-header-top">
          <h2 className="treasury-title" title="Пары казны: обмены и долги, найденные автоматикой">
            Обмены и долги
          </h2>
          <div className="treasury-header-actions">
            <span className="tp-total" title="Сколько пар подходит под текущий фильтр">
              Найдено: {total}
            </span>
          </div>
        </div>
        <div className="ta-filter-row">
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="tp-status" title="Какие пары показывать">
              Статус
            </label>
            <select
              id="tp-status"
              className="ta-filter-input"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="candidate">Ждут решения</option>
              <option value="confirmed">Подтверждённые</option>
              <option value="rejected">Отклонённые</option>
              <option value="">Все</option>
            </select>
          </div>
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="tp-nick" title="Фильтр по нику участника">
              Ник
            </label>
            <input
              id="tp-nick"
              className="ta-filter-input"
              value={nick}
              placeholder="часть ника"
              onChange={(event) => setNick(event.target.value)}
            />
          </div>
        </div>
      </div>

      {message && (
        <div
          className={
            message.type === 'success'
              ? 'treasury-message treasury-message-success'
              : 'treasury-message treasury-message-error'
          }
        >
          {message.text}
        </div>
      )}

      <div className="treasury-note" title="Как это работает">
        Автоматика ищет пары: один и тот же участник, близкие даты, противоположные знаки.
        Пока пара не подтверждена казначеем, операции учитываются как обычно — налог и ресурсы
        не меняются. Подтверждение делает обе операции нейтральными.
      </div>

      {loading && <div className="treasury-empty">Загружаю очередь…</div>}

      {!loading && pairs.length === 0 && (
        <div className="treasury-empty">
          {status === 'candidate'
            ? 'Нет пар, ждущих решения.'
            : 'По этому фильтру пар нет.'}
        </div>
      )}

      {!loading &&
        pairs.map((pair) => (
          <div key={pair.id} className="tp-card">
            <div className="tp-card-head">
              <span className={`tp-status tp-status-${pair.status}`} title={STATUS_HINTS[pair.status]}>
                {STATUS_LABELS[pair.status] ?? pair.status}
              </span>
              <span className="tp-kind" title={KIND_HINTS[pair.kind]}>
                {KIND_LABELS[pair.kind] ?? pair.kind}
              </span>
              {pair.comment && <span className="tp-comment">{pair.comment}</span>}
            </div>

            <div className="tp-sides">
              {renderSide(pair, 'first')}
              <div className="tp-arrow" title="Связь между операциями">⇄</div>
              {renderSide(pair, 'second')}
            </div>

            {pair.status === 'candidate' && (
              <div className="tp-actions">
                {confirmingId === pair.id ? (
                  <>
                    <span className="tp-actions-label" title="Что это за операция">
                      Что это:
                    </span>
                    <button
                      type="button"
                      className="treasury-page-btn"
                      title={KIND_HINTS.exchange}
                      onClick={() => handleConfirm(pair, 'exchange')}
                    >
                      Обмен
                    </button>
                    <button
                      type="button"
                      className="treasury-page-btn"
                      title={KIND_HINTS.loan}
                      onClick={() => handleConfirm(pair, 'loan')}
                    >
                      Долг
                    </button>
                    <button
                      type="button"
                      className="tp-btn-ghost"
                      onClick={() => setConfirmingId(null)}
                    >
                      Отмена
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="treasury-page-btn"
                      onClick={() => setConfirmingId(pair.id)}
                    >
                      Подтвердить
                    </button>
                    <button
                      type="button"
                      className="tp-btn-ghost"
                      onClick={() => handleReject(pair)}
                    >
                      Отклонить
                    </button>
                  </>
                )}
              </div>
            )}

            {pair.status === 'confirmed' && (
              <div className="tp-actions">
                <button
                  type="button"
                  className="tp-btn-ghost"
                  onClick={() => openRevise(pair)}
                >
                  Скорректировать
                </button>
                {pendingUnconfirm === pair.id ? (
                  <>
                    <span className="tp-actions-label">
                      Точно вернуть в учёт?
                    </span>
                    <button
                      type="button"
                      className="treasury-page-btn"
                      onClick={() => handleUnconfirm(pair)}
                    >
                      Да, отменить
                    </button>
                    <button
                      type="button"
                      className="tp-btn-ghost"
                      onClick={() => setPendingUnconfirm(null)}
                    >
                      Нет
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="tp-btn-ghost"
                    onClick={() => setPendingUnconfirm(pair.id)}
                  >
                    Отменить подтверждение
                  </button>
                )}
              </div>
            )}
          </div>
        ))}

      {reviseTarget && (
        <div className="tp-modal-backdrop" onClick={() => setReviseTarget(null)}>
          <div className="tp-modal" onClick={(event) => event.stopPropagation()}>
            <h3 className="tp-modal-title">Корректировка пары</h3>
            <div className="tp-modal-row">
              <label className="tp-modal-label" htmlFor="tp-revise-kind" title="Тип операции">
                Что это
              </label>
              <select
                id="tp-revise-kind"
                className="ta-filter-input"
                value={reviseKind}
                onChange={(event) =>
                  setReviseKind(event.target.value === 'loan' ? 'loan' : 'exchange')
                }
              >
                <option value="exchange">Обмен</option>
                <option value="loan">Долг</option>
              </select>
            </div>
            <div className="tp-modal-row">
              <label className="tp-modal-label" htmlFor="tp-revise-comment" title="Причина правки">
                Комментарий
              </label>
              <input
                id="tp-revise-comment"
                className="ta-filter-input"
                value={reviseComment}
                placeholder="почему меняем"
                onChange={(event) => setReviseComment(event.target.value)}
              />
            </div>
            <div className="tp-modal-actions">
              <button type="button" className="treasury-page-btn" onClick={handleRevise}>
                Сохранить
              </button>
              <button
                type="button"
                className="tp-btn-ghost"
                onClick={() => setReviseTarget(null)}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
