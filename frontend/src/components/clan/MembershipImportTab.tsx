import { useState, useEffect, useCallback } from 'react';
import { getTreasuryCookiesStatus, importMemberDiff, importHistoryEvents, getMembershipEvents } from '../../api/clanInfo';
import type { ClanMemberData, MembershipEvent } from '../../types/clanInfo';
import { Button } from '../ui/Button';
import './MembershipImportTab.css';

interface MembershipImportTabProps {
  clanId: number;
  onImportComplete?: () => void;
}

interface FetchedMember {
  nick: string;
  level?: number;
  game_rank?: string;
  profession?: string;
  profession_level?: number;
  clan_role?: string;
  join_date?: string;
  trial_until?: string;
}

interface LeftMemberInfo {
  nick: string;
  last_seen_level?: number;
  last_seen_role?: string;
}

interface HistoryEvent {
  nick: string;
  event_type: 'joined' | 'left';
  event_date: string;
  leave_reason?: string;
}

const LEAVE_REASONS = ['Вышел сам', 'Исключен', 'Переведен в другой клан', 'Не активен', 'Другое'];

export function MembershipImportTab({ clanId, onImportComplete }: MembershipImportTabProps) {
  const [cookieStatus, setCookieStatus] = useState<{ has_cookies: boolean; is_valid: boolean; updated_at?: string | null }>({ has_cookies: false, is_valid: false });
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isFetching, setIsFetching] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  const [joinedMembers, setJoinedMembers] = useState<FetchedMember[]>([]);
  const [needsUpdateMembers, setNeedsUpdateMembers] = useState<FetchedMember[]>([]);
  const [leftMembers, setLeftMembers] = useState<LeftMemberInfo[]>([]);
  const [historyEvents, setHistoryEvents] = useState<HistoryEvent[]>([]);
  const [leaveReasons, setLeaveReasons] = useState<Record<string, string>>({});

  const [savedEvents, setSavedEvents] = useState<MembershipEvent[]>([]);
  const [showEvents, setShowEvents] = useState(false);

  const [fetchProgress, setFetchProgress] = useState<{
    phase: 'idle' | 'counting' | 'fetching' | 'done' | 'error';
    totalPages: number;
    currentPage: number;
    totalEvents: number;
    elapsed: number;
    message: string;
  }>({ phase: 'idle', totalPages: 0, currentPage: 0, totalEvents: 0, elapsed: 0, message: '' });

  const [eventSource, setEventSource] = useState<EventSource | null>(null);

  useEffect(() => {
    getTreasuryCookiesStatus(clanId).then(setCookieStatus).catch(() => setCookieStatus({ has_cookies: false, is_valid: false }));
  }, [clanId]);

  useEffect(() => {
    if (showEvents) {
      getMembershipEvents(clanId).then(setSavedEvents).catch(() => setSavedEvents([]));
    }
  }, [clanId, showEvents]);

  const refreshCookieStatus = useCallback(() => {
    getTreasuryCookiesStatus(clanId).then(setCookieStatus).catch(() => setCookieStatus({ has_cookies: false, is_valid: false }));
  }, [clanId]);

  const cancelFetch = useCallback(() => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }
    setIsFetching(false);
    setFetchProgress((prev) => ({ ...prev, phase: 'error', message: 'Сбор отменён пользователем' }));
  }, [eventSource]);

  const handleStartFetch = useCallback(() => {
    setIsFetching(true);
    setMessage(null);
    setJoinedMembers([]);
    setLeftMembers([]);
    setHistoryEvents([]);
    setFetchProgress({ phase: 'counting', totalPages: 0, currentPage: 0, totalEvents: 0, elapsed: 0, message: 'Подключение...' });

    const apiBase = import.meta.env.VITE_API_URL || window.location.origin;
    const token = localStorage.getItem('auth_token');
    const url = `${apiBase}/api/clan/${clanId}/members/auto-fetch-stream${token ? `?token=${encodeURIComponent(token)}` : ''}`;

    const es = new EventSource(url);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        switch (data.type) {
          case 'diff':
            setJoinedMembers(data.joined || []);
            setNeedsUpdateMembers(data.needs_update || []);
            setLeftMembers(data.left || []);
            setFetchProgress((prev) => ({
              ...prev,
              phase: 'fetching',
              message: `Diff: ${data.joined?.length || 0} вступили, ${data.left?.length || 0} выбыли. Загрузка истории...`,
            }));
            break;
          case 'counting':
            setFetchProgress({
              phase: 'fetching',
              totalPages: data.total_pages,
              currentPage: 0,
              totalEvents: 0,
              elapsed: 0,
              message: `Найдено ${data.total_pages} страниц истории. Начинаю сбор...`,
            });
            break;
          case 'progress':
            const pct = data.total_pages > 0 ? Math.round(((data.page + 1) / data.total_pages) * 100) : 0;
            setFetchProgress({
              phase: 'fetching',
              totalPages: data.total_pages,
              currentPage: data.page + 1,
              totalEvents: data.total_events,
              elapsed: data.elapsed || 0,
              message: `Страница ${data.page + 1} из ${data.total_pages} (${pct}%) · ${data.total_events} событий`,
            });
            break;
          case 'done':
            setHistoryEvents(data.events || []);
            setFetchProgress({
              phase: 'done',
              totalPages: data.pages_fetched,
              currentPage: data.pages_fetched,
              totalEvents: data.total_events,
              elapsed: data.elapsed,
              message: `Собрано: ${joinedMembers.length + (data.joined?.length || 0)} вступили, ${leftMembers.length + (data.left?.length || 0)} выбыли, ${data.total_events} событий из истории`,
            });
            es.close();
            setEventSource(null);
            setIsFetching(false);
            break;
          case 'error':
            setFetchProgress({
              phase: 'error',
              totalPages: 0,
              currentPage: 0,
              totalEvents: 0,
              elapsed: 0,
              message: data.message || 'Ошибка при сборе данных',
            });
            if (data.reason === 'session_expired') {
              refreshCookieStatus();
            }
            es.close();
            setEventSource(null);
            setIsFetching(false);
            break;
        }
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };

    es.onerror = () => {
      setFetchProgress((prev) => ({
        ...prev,
        phase: 'error',
        message: prev.phase === 'error' ? prev.message : 'Соединение потеряно',
      }));
      es.close();
      setEventSource(null);
      setIsFetching(false);
    };

    setEventSource(es);
  }, [clanId, refreshCookieStatus, joinedMembers.length, leftMembers.length]);

  const handleImport = async () => {
    setIsImporting(true);
    setMessage(null);

    try {
      const leftWithReasons = leftMembers.map((m) => ({
        nick: m.nick,
        leave_reason: leaveReasons[m.nick] || '',
      }));

      const diffResult = await importMemberDiff(clanId, {
        joined: [...joinedMembers, ...needsUpdateMembers],
        left: leftWithReasons,
      });

      const historyResult = await importHistoryEvents(clanId, historyEvents);

      const totalJoined = diffResult.joined_count + historyResult.processed_count;
      const totalLeft = diffResult.left_count;

      setMessage({
        type: 'success',
        text: `Импортировано: ${totalJoined} вступлений, ${totalLeft} выходов. Событий из истории: ${historyResult.processed_count}`,
      });

      setJoinedMembers([]);
      setNeedsUpdateMembers([]);
      setLeftMembers([]);
      setHistoryEvents([]);
      setLeaveReasons({});
      setFetchProgress({ phase: 'idle', totalPages: 0, currentPage: 0, totalEvents: 0, elapsed: 0, message: '' });
      onImportComplete?.();
    } catch (err) {
      setMessage({ type: 'error', text: `Ошибка: ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setIsImporting(false);
    }
  };

  const handleClear = () => {
    setJoinedMembers([]);
    setNeedsUpdateMembers([]);
    setLeftMembers([]);
    setHistoryEvents([]);
    setLeaveReasons({});
    setFetchProgress({ phase: 'idle', totalPages: 0, currentPage: 0, totalEvents: 0, elapsed: 0, message: '' });
    setMessage(null);
  };

  const formatCookieDate = (iso?: string | null) => {
    if (!iso) return '?';
    const d = new Date(iso);
    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

  const hasResults = joinedMembers.length > 0 || needsUpdateMembers.length > 0 || leftMembers.length > 0 || historyEvents.length > 0;

  return (
    <div className="membership-import-tab">
      {message && (
        <div className={`membership-message membership-message-${message.type}`}>
          {message.text}
        </div>
      )}

      <section className="membership-section">
        <h3 className="membership-section-title">Авторизация на dwar.ru</h3>
        <div className="membership-cookie-status">
          {cookieStatus.has_cookies ? (
            <>
              <span className={`cookie-status-badge ${cookieStatus.is_valid ? 'valid' : 'invalid'}`}>
                {cookieStatus.is_valid ? 'Cookies активны' : 'Cookies недействительны'}
              </span>
              <span className="cookie-status-date">
                Обновлены: {formatCookieDate(cookieStatus.updated_at)}
              </span>
            </>
          ) : (
            <span className="cookie-status-badge none">Cookies не настроены — используйте вкладку «Авто-импорт (cookies)»</span>
          )}
        </div>
      </section>

      {cookieStatus.has_cookies && cookieStatus.is_valid && (
        <>
          <section className="membership-section">
            <h3 className="membership-section-title">Сбор данных о членстве</h3>
            <div className="membership-fetch-info">
              <p>Данные будут собраны с <strong>01.01.2025</strong> по текущую дату.</p>
              <p>Режимы: Diff состава + История клана</p>
            </div>

            {fetchProgress.phase === 'idle' && (
              <Button variant="primary" onClick={handleStartFetch}>
                Начать сбор
              </Button>
            )}

            {isFetching && (
              <div className="membership-fetch-progress">
                <div className="progress-bar-container">
                  <div className="progress-bar">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${fetchProgress.totalPages > 0 ? (fetchProgress.currentPage / fetchProgress.totalPages) * 100 : 0}%` }}
                    />
                  </div>
                  <span className="progress-percentage">
                    {fetchProgress.totalPages > 0 ? Math.round((fetchProgress.currentPage / fetchProgress.totalPages) * 100) : 0}%
                  </span>
                </div>
                <div className="progress-details">
                  <span className="progress-text">{fetchProgress.message}</span>
                </div>
                <Button variant="danger" size="small" onClick={cancelFetch}>
                  Отменить
                </Button>
              </div>
            )}

            {!isFetching && fetchProgress.phase === 'error' && fetchProgress.message && (
              <div className="membership-fetch-error">
                <p>{fetchProgress.message}</p>
                {fetchProgress.totalPages === 0 && (
                  <Button variant="secondary" size="small" onClick={handleStartFetch}>
                    Попробовать снова
                  </Button>
                )}
              </div>
            )}
          </section>

          {hasResults && fetchProgress.phase === 'done' && (
            <>
              {(joinedMembers.length > 0 || leftMembers.length > 0) && (
                <section className="membership-section">
                  <h3 className="membership-section-title">Изменения состава (Diff)</h3>

                  {joinedMembers.length > 0 && (
                    <div className="membership-diff-group">
                      <h4 className="diff-group-title diff-group-joined">
                        Вступили ({joinedMembers.length})
                      </h4>
                      <table className="membership-table">
                        <thead>
                          <tr>
                            <th>Ник</th>
                            <th>Уровень</th>
                            <th>Ранг</th>
                            <th>Роль</th>
                            <th>Дата вступления</th>
                          </tr>
                        </thead>
                        <tbody>
                          {joinedMembers.map((m, i) => (
                            <tr key={i} className="row-joined">
                              <td><span className="status-badge status-joined">+</span> {m.nick}</td>
                              <td>{m.level || '?'}</td>
                              <td>{m.game_rank || '—'}</td>
                              <td>{m.clan_role || '—'}</td>
                              <td>{m.join_date || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {needsUpdateMembers.length > 0 && (
                    <div className="membership-diff-group">
                      <h4 className="diff-group-title diff-group-update">
                        Обновить даты вступления ({needsUpdateMembers.length})
                      </h4>
                      <table className="membership-table">
                        <thead>
                          <tr>
                            <th>Ник</th>
                            <th>Уровень</th>
                            <th>Ранг</th>
                            <th>Дата вступления</th>
                          </tr>
                        </thead>
                        <tbody>
                          {needsUpdateMembers.map((m, i) => (
                            <tr key={i} className="row-update">
                              <td><span className="status-badge status-update">~</span> {m.nick}</td>
                              <td>{m.level || '?'}</td>
                              <td>{m.game_rank || '—'}</td>
                              <td>{m.join_date || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {leftMembers.length > 0 && (
                    <div className="membership-diff-group">
                      <h4 className="diff-group-title diff-group-left">
                        Выбыли ({leftMembers.length})
                      </h4>
                      <table className="membership-table">
                        <thead>
                          <tr>
                            <th>Ник</th>
                            <th>Уровень</th>
                            <th>Последняя роль</th>
                            <th>Причина</th>
                          </tr>
                        </thead>
                        <tbody>
                          {leftMembers.map((m, i) => (
                            <tr key={i} className="row-left">
                              <td><span className="status-badge status-left">−</span> {m.nick}</td>
                              <td>{m.last_seen_level || '?'}</td>
                              <td>{m.last_seen_role || '—'}</td>
                              <td>
                                <select
                                  className="leave-reason-select"
                                  value={leaveReasons[m.nick] || ''}
                                  onChange={(e) => setLeaveReasons((prev) => ({ ...prev, [m.nick]: e.target.value }))}
                                >
                                  <option value="">Выберите</option>
                                  {LEAVE_REASONS.map((r) => (
                                    <option key={r} value={r}>{r}</option>
                                  ))}
                                </select>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              )}

              {historyEvents.length > 0 && (
                <section className="membership-section">
                  <h3 className="membership-section-title">
                    События из истории ({historyEvents.length})
                  </h3>
                  <table className="membership-table">
                    <thead>
                      <tr>
                        <th>Дата</th>
                        <th>Ник</th>
                        <th>Событие</th>
                        <th>Причина</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historyEvents.map((ev, i) => (
                        <tr key={i} className={ev.event_type === 'joined' ? 'row-joined' : 'row-left'}>
                          <td>{ev.event_date}</td>
                          <td>
                            <span className={`status-badge status-${ev.event_type}`}>
                              {ev.event_type === 'joined' ? '+' : '−'}
                            </span>
                            {' '}{ev.nick}
                          </td>
                          <td>{ev.event_type === 'joined' ? 'Принят в клан' : 'Покинул клан'}</td>
                          <td>{ev.leave_reason || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}

              <div className="membership-actions">
                <Button variant="secondary" onClick={handleClear}>
                  Сбросить
                </Button>
                <Button variant="primary" onClick={handleImport} disabled={isImporting}>
                  {isImporting
                    ? 'Импорт...'
                    : `Импортировать (${joinedMembers.length} вступлений, ${needsUpdateMembers.length} обновлений дат, ${leftMembers.length} выходов, ${historyEvents.length} событий)`}
                </Button>
              </div>
            </>
          )}
        </>
      )}

      <section className="membership-section">
        <button
          className="toggle-events-btn"
          onClick={() => setShowEvents(!showEvents)}
        >
          {showEvents ? 'Скрыть сохранённые события' : 'Показать сохранённые события'}
        </button>

        {showEvents && savedEvents.length > 0 && (
          <table className="membership-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Ник</th>
                <th>Событие</th>
                <th>Источник</th>
                <th>Причина</th>
              </tr>
            </thead>
            <tbody>
              {savedEvents.map((e) => (
                <tr key={e.id} className={e.event_type === 'joined' ? 'row-joined' : 'row-left'}>
                  <td>{e.event_date}</td>
                  <td>{e.nick}</td>
                  <td>{e.event_type === 'joined' ? 'Вступил' : 'Выбыл'}</td>
                  <td>{e.source}</td>
                  <td>{e.leave_reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {showEvents && savedEvents.length === 0 && (
          <p className="no-events">Нет сохранённых событий</p>
        )}
      </section>
    </div>
  );
}
