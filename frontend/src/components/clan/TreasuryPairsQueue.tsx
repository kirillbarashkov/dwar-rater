import { useCallback, useEffect, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  batchDecideTreasuryPairs,
  confirmTreasuryPair,
  getTreasuryPairHistory,
  getTreasuryPairs,
  rejectTreasuryPair,
  restoreTreasuryPair,
  reviseTreasuryPair,
  splitTreasuryPair,
  unconfirmTreasuryPair,
} from '../../api/treasuryPairs';
import { addExclusionRule, getExclusionGroups } from '../../api/treasuryExclusions';
import type { ExclusionGroup } from '../../types/treasuryExclusions';
import type {
  TreasuryPairData,
  TreasuryPairHistoryEntry,
} from '../../types/treasuryPairs';
import './TreasuryPairsQueue.css';

const KIND_LABELS: Record<string, string> = {
  exchange: 'Обмен',
  loan: 'Долг',
};

const MODE_LABELS: Record<string, string> = {
  exclude: 'исключить из отчётов',
  neutral: 'нейтральные',
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

/** Сколько пар показывать на странице. Очередь на проде — тысячи записей, тянуть всё сразу незачем. */
const PAGE_SIZE = 50;

/** Человеческие названия действий из аудита — в истории нужен смысл, а не код. */
const ACTION_LABELS: Record<string, string> = {
  revision: 'Правка пары',
  treasury_pair_confirm: 'Подтвердил пару',
  treasury_pair_reject: 'Отклонил пару',
  treasury_pair_unconfirm: 'Отменил подтверждение',
  treasury_pair_revise: 'Скорректировал пару',
  treasury_pair_split: 'Разорвал пару (списание на таланты)',
  treasury_pair_restore: 'Вернул в очередь',
};

interface Props {
  clanId: number;
}

export function TreasuryPairsQueue({ clanId }: Props) {
  const [pairs, setPairs] = useState<TreasuryPairData[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState('candidate');
  const [nick, setNick] = useState('');
  const [kind, setKind] = useState('');
  const [opType, setOpType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sort, setSort] = useState('old');
  const [offset, setOffset] = useState(0);
  const [historyFor, setHistoryFor] = useState<TreasuryPairData | null>(null);
  const [historyEntries, setHistoryEntries] = useState<TreasuryPairHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [batchKind, setBatchKind] = useState<'exchange' | 'loan'>('exchange');
  const [batchBusy, setBatchBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(
    null,
  );
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [pendingUnconfirm, setPendingUnconfirm] = useState<number | null>(null);
  const [reviseTarget, setReviseTarget] = useState<TreasuryPairData | null>(null);
  const [reviseKind, setReviseKind] = useState<'exchange' | 'loan'>('exchange');
  const [reviseComment, setReviseComment] = useState('');

  const [searchParams, setSearchParams] = useSearchParams();
  // Переход из «Статуса персонажа»: ?pair=<id> показывает ровно эту пару.
  const focusPairId = Number(searchParams.get('pair')) || null;
  const [menu, setMenu] = useState<{
    x: number;
    y: number;
    objectName: string;
    alternatives: string[];
  } | null>(null);
  const [groups, setGroups] = useState<ExclusionGroup[]>([]);

  // Escape закрывает меню, клик мимо ловит подложка (.tp-ctx-backdrop). Слушатель
  // на window тут вреден: он гасил меню и на кликах ВНУТРИ него, из-за чего
  // переключатель объекта не работал — меню просто исчезало.
  useEffect(() => {
    if (!menu) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenu(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menu]);

  const clearFocus = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('pair');
    setSearchParams(next);
  };

  const objectNames = (pair: TreasuryPairData): string[] => {
    const names = [pair.first?.object_name, pair.second?.object_name]
      .map((name) => (name || '').trim())
      .filter(Boolean);
    return Array.from(new Set(names));
  };

  // «Монеты» — это деньги: исключить их значит выкинуть из отчётов всю казну.
  // Поэтому по умолчанию предлагаем ресурсную сторону, а не денежную.
  const defaultObject = (pair: TreasuryPairData): string => {
    const sides = [pair.first, pair.second].filter(Boolean);
    const resource = sides.find((side) => (side?.operation_type || '') !== 'Деньги');
    return (resource ?? sides[sides.length - 1])?.object_name || '';
  };

  const openMenu = (
    x: number,
    y: number,
    objectName: string,
    alternatives: string[],
  ) => {
    if (!objectName) return;
    setMenu({ x, y, objectName, alternatives });
    if (groups.length === 0) {
      getExclusionGroups(clanId)
        .then((data) => setGroups(data.items.filter((group) => group.is_active)))
        .catch(() => setGroups([]));
    }
  };

  const openContextMenu = (
    event: ReactMouseEvent,
    pair: TreasuryPairData,
    objectName: string,
  ) => {
    event.preventDefault();
    openMenu(event.clientX, event.clientY, objectName, objectNames(pair));
  };

  // Видимая кнопка в ряду действий: контекстное меню само по себе невидимо, и
  // найти его на узком названии объекта нереально — казначей просто не знал, что
  // оно есть. Кнопка открывает то же меню, правая кнопка остаётся быстрым путём.
  const openMenuFromButton = (event: ReactMouseEvent, pair: TreasuryPairData) => {
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    openMenu(rect.left, rect.bottom + 4, defaultObject(pair), objectNames(pair));
  };

  const addToGroup = async (group: ExclusionGroup) => {
    if (!menu) return;
    const objectName = menu.objectName;
    setMenu(null);
    try {
      const result = await addExclusionRule(clanId, group.id, objectName);
      setMessage({
        type: 'success',
        text: `«${objectName}» добавлен в группу «${group.name}» (${MODE_LABELS[group.mode] ?? group.mode}). Пересчитано операций: ${result.changed}.`,
      });
      await load();
    } catch (error) {
      const text = (error as { response?: { data?: { error?: string } } })?.response?.data
        ?.error;
      setMessage({ type: 'error', text: text || 'Не удалось добавить объект в группу' });
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTreasuryPairs(clanId, {
        status: status || undefined,
        kind: kind || undefined,
        nick: nick.trim() || undefined,
        op_type: opType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        sort,
        pair_id: focusPairId ?? undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setPairs(data.items);
      setTotal(data.total);
    } catch {
      setMessage({ type: 'error', text: 'Не удалось загрузить очередь пар' });
    } finally {
      setLoading(false);
    }
  }, [clanId, status, kind, nick, opType, dateFrom, dateTo, sort, offset, focusPairId]);

  // Смена фильтров возвращает на первую страницу: иначе легко оказаться
  // на странице, которой у нового отбора уже нет.
  useEffect(() => {
    setOffset(0);
  }, [status, kind, nick, opType, dateFrom, dateTo, sort]);

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

  const toggleSelect = (pairId: number) => {
    setSelected((prev) =>
      prev.includes(pairId) ? prev.filter((id) => id !== pairId) : [...prev, pairId],
    );
  };

  const candidates = pairs.filter((pair) => pair.status === 'candidate');

  const toggleAll = () => {
    const ids = candidates.map((pair) => pair.id);
    setSelected((prev) => (prev.length === ids.length ? [] : ids));
  };

  const handleBatch = async (action: 'confirm' | 'reject') => {
    if (selected.length === 0) return;
    setBatchBusy(true);
    try {
      const result = await batchDecideTreasuryPairs(
        clanId,
        selected,
        action,
        action === 'confirm' ? batchKind : undefined,
      );
      const label = action === 'confirm' ? `подтверждено (${KIND_LABELS[batchKind]})` : 'отклонено';
      const failed = result.failed.length
        ? ` Не прошло: ${result.failed.length} — ${result.failed
            .map((item) => `#${item.id}: ${item.error}`)
            .join('; ')}`
        : '';
      setMessage({
        type: result.failed.length ? 'error' : 'success',
        text: `Групповое действие: ${label} — ${result.done.length} пар.${failed}`,
      });
      setSelected([]);
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось выполнить групповое действие' });
    } finally {
      setBatchBusy(false);
    }
  };

  const openHistory = async (pair: TreasuryPairData) => {
    setHistoryFor(pair);
    setHistoryEntries([]);
    setHistoryLoading(true);
    try {
      const data = await getTreasuryPairHistory(clanId, pair.id);
      setHistoryEntries(data.entries);
    } catch {
      setMessage({ type: 'error', text: 'Не удалось загрузить историю пары' });
      setHistoryFor(null);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleRestore = async (pair: TreasuryPairData) => {
    try {
      await restoreTreasuryPair(clanId, pair.id);
      setMessage({
        type: 'success',
        text: 'Пара вернулась в очередь кандидатов. Операции снова учитываются в налоге и ресурсах.',
      });
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось вернуть пару в очередь' });
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

  const handleSplit = async (pair: TreasuryPairData, keep: 'first' | 'second') => {
    try {
      await splitTreasuryPair(clanId, pair.id, keep);
      setMessage({
        type: 'success',
        text: 'Операция помечена как списание на таланты клана. Вторая сторона вернулась в очередь кандидатов.',
      });
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось разорвать пару' });
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
          <span
            className="tp-side-object"
            title="Правая кнопка — добавить объект в группу исключений"
            onContextMenu={(event) => openContextMenu(event, pair, side.object_name)}
          >
            {side.object_name}
          </span>
          <span
            className={side.quantity < 0 ? 'tp-side-qty tp-side-qty-out' : 'tp-side-qty tp-side-qty-in'}
          >
            {side.quantity > 0 ? `+${side.quantity}` : side.quantity}
          </span>
        </div>
        {side.op_class === 'neutral' ? (
          <div className="tp-side-flag" title={NEUTRAL_HINT}>
            {side.class_kind === 'talents' ? 'списание на таланты клана' : 'нейтральная'}
          </div>
        ) : (
          pair.status === 'candidate' && (
            <button
              type="button"
              className="tp-split-btn"
              title="Эта операция — списание на таланты клана (делает глава или совет). Пара распадётся: вторая сторона вернётся в очередь кандидатов."
              onClick={() => handleSplit(pair, which)}
            >
              удалить карточку → таланты
            </button>
          )
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
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="tp-kind" title="Что это: обмен или долг">
              Тип пары
            </label>
            <select
              id="tp-kind"
              className="ta-filter-input"
              value={kind}
              onChange={(event) => setKind(event.target.value)}
            >
              <option value="">Любой</option>
              <option value="exchange">Обмен</option>
              <option value="loan">Долг</option>
            </select>
          </div>
          <div className="ta-filter-group">
            <label
              className="ta-filter-label"
              htmlFor="tp-optype"
              title="Тип операции на любой стороне пары: так отделяются деньги от ресурсов"
            >
              Операция
            </label>
            <select
              id="tp-optype"
              className="ta-filter-input"
              value={opType}
              onChange={(event) => setOpType(event.target.value)}
            >
              <option value="">Любая</option>
              <option value="Деньги">Деньги</option>
              <option value="Предмет">Предмет</option>
            </select>
          </div>
          <div className="ta-filter-group">
            <label
              className="ta-filter-label"
              htmlFor="tp-from"
              title="Показывать пары с операциями не раньше этого месяца"
            >
              Период с
            </label>
            <input
              id="tp-from"
              className="ta-filter-input"
              type="month"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </div>
          <div className="ta-filter-group">
            <label
              className="ta-filter-label"
              htmlFor="tp-to"
              title="Показывать пары с операциями не позже этого месяца"
            >
              по
            </label>
            <input
              id="tp-to"
              className="ta-filter-input"
              type="month"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </div>
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="tp-sort" title="Порядок разбора очереди">
              Порядок
            </label>
            <select
              id="tp-sort"
              className="ta-filter-input"
              value={sort}
              onChange={(event) => setSort(event.target.value)}
            >
              <option value="old">По порядку импорта</option>
              <option value="new">Сначала новые</option>
            </select>
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
          <div
            key={pair.id}
            className={`tp-card ${focusPairId === pair.id ? 'tp-card-focus' : ''}`}
          >
            <div className="tp-card-head">
              {pair.status === 'candidate' && (
                <input
                  type="checkbox"
                  className="tp-check"
                  title="Отметить для группового действия"
                  checked={selected.includes(pair.id)}
                  onChange={() => toggleSelect(pair.id)}
                />
              )}
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

            {pair.status === 'candidate' ? (
              <div className="tp-actions">
                <button
                  type="button"
                  className="tp-btn-ghost"
                  title="Объект из этой пары — в группу исключений: он перестанет попадать в отчёты казны"
                  onClick={(event) => openMenuFromButton(event, pair)}
                >
                  в группу исключений
                </button>
                <button
                  type="button"
                  className="tp-btn-ghost"
                  title="Кто и когда менял эту пару"
                  onClick={() => openHistory(pair)}
                >
                  История
                </button>
              </div>
            ) : (
              <div className="tp-actions">
                <button
                  type="button"
                  className="tp-btn-ghost"
                  title="Объект из этой пары — в группу исключений: он перестанет попадать в отчёты казны"
                  onClick={(event) => openMenuFromButton(event, pair)}
                >
                  в группу исключений
                </button>
                <button
                  type="button"
                  className="tp-btn-ghost"
                  title="Вернуть пару в очередь кандидатов: операции снова начнут учитываться"
                  onClick={() => handleRestore(pair)}
                >
                  Вернуть в очередь
                </button>
                <button
                  type="button"
                  className="tp-btn-ghost"
                  title="Кто и когда менял эту пару"
                  onClick={() => openHistory(pair)}
                >
                  История
                </button>
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

      {focusPairId !== null && (
        <div className="tp-focus" title="Переход из вкладки «Статус персонажа»">
          <span className="tp-focus-text">
            Показана одна пара: #{focusPairId}. Её можно проверить и подтвердить.
          </span>
          <button type="button" className="tp-btn-ghost" onClick={clearFocus}>
            Показать всю очередь
          </button>
        </div>
      )}

      {!loading && candidates.length > 0 && (
        <div className="tp-batch" title="Групповое действие применяется ко всем отмеченным парам">
          <button type="button" className="tp-btn-ghost" onClick={toggleAll}>
            {selected.length === candidates.length && candidates.length > 0
              ? 'Снять выбор'
              : `Выбрать все на странице (${candidates.length})`}
          </button>
          <span className="tp-batch-count">Отмечено: {selected.length}</span>
          <span className="tp-actions-label">Что это:</span>
          <select
            className="ta-filter-input tp-batch-kind"
            value={batchKind}
            onChange={(event) =>
              setBatchKind(event.target.value === 'loan' ? 'loan' : 'exchange')
            }
          >
            <option value="exchange">Обмен</option>
            <option value="loan">Долг</option>
          </select>
          <button
            type="button"
            className="treasury-page-btn"
            disabled={selected.length === 0 || batchBusy}
            onClick={() => handleBatch('confirm')}
          >
            Подтвердить отмеченные
          </button>
          <button
            type="button"
            className="tp-btn-ghost"
            disabled={selected.length === 0 || batchBusy}
            onClick={() => handleBatch('reject')}
          >
            Отклонить отмеченные
          </button>
        </div>
      )}

      {!loading && total > PAGE_SIZE && (
        <div className="tp-pagination">
          <button
            type="button"
            className="tp-btn-ghost"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            ← Назад
          </button>
          <span className="tp-page-info" title="Сколько пар показано из общего числа">
            Страница {Math.floor(offset / PAGE_SIZE) + 1} из {Math.ceil(total / PAGE_SIZE)}
            {' · '}показано {pairs.length} из {total}
          </span>
          <button
            type="button"
            className="tp-btn-ghost"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Вперёд →
          </button>
        </div>
      )}

      {historyFor && (
        <div className="tp-modal-backdrop" onClick={() => setHistoryFor(null)}>
          <div
            className="tp-modal tp-modal-wide"
            onClick={(event) => event.stopPropagation()}
          >
            <h3 className="tp-modal-title">История пары #{historyFor.id}</h3>

            {historyLoading && <div className="treasury-empty">Загружаю историю…</div>}

            {!historyLoading && historyEntries.length === 0 && (
              <div className="treasury-empty">Решений по этой паре пока не было.</div>
            )}

            {!historyLoading && historyEntries.length > 0 && (
              <div className="tp-history">
                {historyEntries.map((entry, index) => (
                  <div key={`${entry.source}-${index}`} className="tp-history-row">
                    <div className="tp-history-head">
                      <span className="tp-history-action">
                        {ACTION_LABELS[entry.action] ?? entry.action}
                      </span>
                      <span className="tp-history-who">{entry.changed_by_name}</span>
                      <span className="tp-history-when">
                        {entry.at ? entry.at.replace('T', ' ').slice(0, 16) : '—'}
                      </span>
                    </div>
                    {entry.comment && (
                      <div className="tp-history-comment">{entry.comment}</div>
                    )}
                    <div className="tp-history-values" title="Что было и что стало">
                      {entry.old && (
                        <span className="tp-history-old">было: {entry.old}</span>
                      )}
                      {entry.new && (
                        <span className="tp-history-new">стало: {entry.new}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="tp-modal-actions">
              <button
                type="button"
                className="tp-btn-ghost"
                onClick={() => setHistoryFor(null)}
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

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

      {menu && (
        <>
          <div
            className="tp-ctx-backdrop"
            onClick={() => setMenu(null)}
            onContextMenu={(event) => {
              event.preventDefault();
              setMenu(null);
            }}
          />
          <div className="tp-ctxmenu" style={{ left: menu.x, top: menu.y }}>
            <div className="tp-ctxmenu-title">Добавить в группу исключений</div>
            <div
              className="tp-ctxmenu-object"
              title="Правило сопоставляется по началу названия — «Сущность» поймает и «Сущность кретса»"
            >
              {menu.objectName}
            </div>
            {menu.alternatives.filter((name) => name !== menu.objectName).length > 0 && (
              <div className="tp-ctxmenu-alt">
                <span className="tp-ctxmenu-alt-label">Взять другой объект пары:</span>
                {menu.alternatives
                  .filter((name) => name !== menu.objectName)
                  .map((name) => (
                    <button
                      key={name}
                      type="button"
                      className="tp-ctxmenu-alt-btn"
                      onClick={() => setMenu({ ...menu, objectName: name })}
                    >
                      {name}
                    </button>
                  ))}
              </div>
            )}
            {groups.length === 0 ? (
              <div className="tp-ctxmenu-empty">
                Групп нет — создайте их во вкладке «Группы исключений»
              </div>
            ) : (
              groups.map((group) => (
                <button
                  key={group.id}
                  type="button"
                  className="tp-ctxmenu-item"
                  onClick={() => addToGroup(group)}
                  title={`Режим группы: ${MODE_LABELS[group.mode] ?? group.mode}`}
                >
                  <span>{group.name}</span>
                  <span className="tp-ctxmenu-mode">
                    {MODE_LABELS[group.mode] ?? group.mode}
                  </span>
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
