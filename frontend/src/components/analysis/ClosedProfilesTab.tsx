import { useState, useEffect, useRef } from 'react';
import type { ClosedProfileData, CheckResult } from '../../types/closedProfile';
import type { AnalysisResult } from '../../types/character';
import {
  getClosedProfiles,
  addClosedProfile,
  updateClosedProfile,
  deleteClosedProfile,
  checkProfile,
  batchScan,
  batchDelete,
  deleteAllClosedProfiles,
  saveSnapshotForProfile,
} from '../../api/closedProfiles';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Modal } from '../ui/Modal';
import { showToast } from '../ui/Toast';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import './ClosedProfilesTab.css';

const CHECK_DURATION = 15;

const GAME_RANKS: Record<number, string> = {
  1: 'Рекрут', 2: 'Солдат', 3: 'Боец', 4: 'Воин', 5: 'Элитный воин',
  6: 'Чемпион', 7: 'Гладиатор', 8: 'Полководец', 9: 'Мастер войны',
  10: 'Герой', 11: 'Военный эксперт', 12: 'Магистр войны', 13: 'Вершитель',
  14: 'Высший магистр', 15: 'Повелитель', 16: 'Легендарный завоеватель',
  17: 'Властелин боя', 18: 'Победоносец', 19: 'Триумфатор', 20: 'Избранник богов',
};

export function ClosedProfilesTab() {
  const [profiles, setProfiles] = useState<ClosedProfileData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showAddModal, setShowAddModal] = useState(false);
  const [addNick, setAddNick] = useState('');
  const [checkingNick, setCheckingNick] = useState<string | null>(null);
  const [checkTimer, setCheckTimer] = useState(CHECK_DURATION);
  const [scanResult, setScanResult] = useState<CheckResult | null>(null);
  const [showResultModal, setShowResultModal] = useState(false);
  const [showNotesModal, setShowNotesModal] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ClosedProfileData | null>(null);
  const [editNotes, setEditNotes] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [scanResults, setScanResults] = useState<Array<{ nick: string; status: string; data?: AnalysisResult }>>([]);
  const [showBatchResults, setShowBatchResults] = useState(false);
  const checkIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { loadProfiles(); }, []);

  useEffect(() => {
    if (checkingNick) {
      setCheckTimer(CHECK_DURATION);
      checkIntervalRef.current = setInterval(() => {
        setCheckTimer(prev => {
          if (prev <= 1) {
            if (checkIntervalRef.current) clearInterval(checkIntervalRef.current);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (checkIntervalRef.current) clearInterval(checkIntervalRef.current);
    };
  }, [checkingNick]);

  const loadProfiles = async () => {
    try {
      const data = await getClosedProfiles();
      setProfiles(data);
    } catch { /* ignore */ }
    finally { setIsLoading(false); }
  };

  const handleAdd = async () => {
    if (!addNick.trim()) return;
    try {
      const result = await addClosedProfile(addNick.trim());
      if ('exists' in result) {
        if (result.is_scanned_open && result.scanned_open_at) {
          const date = new Date(result.scanned_open_at).toLocaleDateString('ru-RU');
          showToast(`Персонаж отсканирован открытым ${date}`, 'info');
        } else {
          showToast('Персонаж уже добавлен', 'warning');
        }
      } else {
        setProfiles(prev => [...prev, result as ClosedProfileData]);
        showToast(`Персонаж ${addNick.trim()} добавлен`, 'success');
      }
      setShowAddModal(false);
      setAddNick('');
    } catch { /* ignore */ }
  };

  const handleCheck = async (nick: string) => {
    setCheckingNick(nick);
    try {
      const resultPromise = checkProfile(nick);
      const minWait = new Promise(resolve => setTimeout(resolve, CHECK_DURATION * 1000));
      const [result] = await Promise.all([resultPromise, minWait]);
      setScanResult(result);
      if (result.status === 'opened') {
        setShowResultModal(true);
        showToast(`${nick} — профиль открыт!`, 'success');
      } else if (result.status === 'closed') {
        showToast(`${nick} — профиль всё ещё закрыт`, 'info');
      } else {
        showToast(`Ошибка проверки ${nick}: ${result.error}`, 'error');
      }
      await loadProfiles();
    } catch {
      showToast('Ошибка при проверке', 'error');
    } finally {
      setCheckingNick(null);
    }
  };

  const handleSaveSnapshot = async (nick: string) => {
    if (!scanResult?.data) return;
    try {
      await saveSnapshotForProfile(nick, scanResult.data as Record<string, unknown>, `${nick} - открытый профиль`);
      showToast('Слепок сохранён', 'success');
      await loadProfiles();
      setShowResultModal(false);
    } catch { /* ignore */ }
  };

  const handleBatchScan = async (nicks?: string[]) => {
    const targetNicks = nicks || profiles.filter(p => !p.is_scanned_open).map(p => p.nick);
    if (targetNicks.length === 0) {
      showToast('Нет персонажей для сканирования', 'info');
      return;
    }
    setIsScanning(true);
    try {
      const result = await batchScan(targetNicks);
      const opened = result.results.filter(r => r.status === 'opened');
      const stillClosed = result.results.filter(r => r.status === 'closed');
      setScanResults(result.results.map(r => ({
        nick: r.nick,
        status: r.status,
        data: r.data as AnalysisResult | undefined,
      })));
      setShowBatchResults(true);
      await loadProfiles();
      if (opened.length > 0) {
        showToast(`Открылось: ${opened.length}, Всё ещё закрыт: ${stillClosed.length}`, 'success');
      } else {
        showToast(`Все ещё закрыты: ${stillClosed.length}`, 'info');
      }
    } catch { /* ignore */ }
    finally { setIsScanning(false); }
  };

  const handleBatchDelete = async (ids?: number[]) => {
    const targetIds = ids || profiles.map(p => p.id);
    if (targetIds.length === 0) return;
    try {
      if (ids) {
        await batchDelete(targetIds);
      } else {
        await deleteAllClosedProfiles();
      }
      setSelected(new Set());
      await loadProfiles();
      showToast('Удалено', 'success');
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteClosedProfile(id);
      setSelected(prev => { const next = new Set(prev); next.delete(id); return next; });
      await loadProfiles();
    } catch { /* ignore */ }
  };

  const handleEditNotes = (profile: ClosedProfileData) => {
    setEditingProfile(profile);
    setEditNotes(profile.notes || '');
    setShowNotesModal(true);
  };

  const handleSaveNotes = async () => {
    if (!editingProfile) return;
    try {
      await updateClosedProfile(editingProfile.id, { notes: editNotes });
      await loadProfiles();
      setShowNotesModal(false);
    } catch { /* ignore */ }
  };

  const toggleSelect = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === profiles.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(profiles.map(p => p.id)));
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString('ru-RU');
  };

  const getRankName = (rankStr: string | null): string => {
    if (!rankStr) return '—';
    const rankId = parseInt(rankStr, 10);
    return GAME_RANKS[rankId] || rankStr;
  };

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="closed-profiles">
      <div className="cp-toolbar">
        <div className="cp-toolbar-left">
          <Button variant="primary" onClick={() => setShowAddModal(true)}>+ Добавить</Button>
          <Button
            variant="secondary"
            onClick={() => handleBatchScan()}
            disabled={isScanning || profiles.length === 0}
          >
            {isScanning ? 'Сканирование...' : 'Сканировать всех'}
          </Button>
          {selected.size > 0 && (
            <Button
              variant="secondary"
              onClick={() => handleBatchScan(profiles.filter(p => selected.has(p.id)).map(p => p.nick))}
              disabled={isScanning}
            >
              Сканировать выбранных ({selected.size})
            </Button>
          )}
        </div>
        <div className="cp-toolbar-right">
          {selected.size > 0 && (
            <Button
              variant="danger"
              onClick={() => handleBatchDelete(Array.from(selected))}
            >
              Удалить выбранных ({selected.size})
            </Button>
          )}
          {profiles.length > 0 && (
            <Button
              variant="danger"
              onClick={() => { if (window.confirm('Удалить всех закрытых персонажей?')) handleBatchDelete(); }}
            >
              Удалить всех
            </Button>
          )}
        </div>
      </div>

      {profiles.length === 0 ? (
        <div className="cp-empty">
          <div className="cp-empty-icon">🔒</div>
          <p>Нет закрытых персонажей</p>
          <p className="cp-empty-hint">Закрытые персонажи добавляются автоматически при анализе или вручную</p>
        </div>
      ) : (
        <table className="cp-table">
          <thead>
            <tr>
              <th className="cp-check">
                <input
                  type="checkbox"
                  checked={selected.size === profiles.length && profiles.length > 0}
                  onChange={toggleSelectAll}
                />
              </th>
              <th>Ник</th>
              <th>Уровень</th>
              <th>Звание</th>
              <th>Клан</th>
              <th>Статус</th>
              <th>Проверок</th>
              <th>Последняя проверка</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {profiles.map(p => (
              <tr key={p.id} className={p.is_scanned_open ? 'cp-row-scanned' : ''}>
                <td className="cp-check">
                  <input
                    type="checkbox"
                    checked={selected.has(p.id)}
                    onChange={() => toggleSelect(p.id)}
                  />
                </td>
                <td className="cp-nick">
                  {p.nick}
                  {p.is_scanned_open && (
                    <span className="cp-scanned-chip" title={`Отсканирован ${formatDate(p.scanned_open_at)}`}>
                      ✓
                    </span>
                  )}
                </td>
                <td>{p.level || '—'}</td>
                <td>{getRankName(p.rank)}</td>
                <td>{p.clan || '—'}</td>
                <td>
                  <span className={`cp-status cp-status-${p.status}`}>
                    {p.status === 'opened' ? 'Открыт' : 'Закрыт'}
                  </span>
                </td>
                <td>{p.check_count}</td>
                <td className="cp-date">{formatDate(p.last_checked)}</td>
                <td className="cp-actions">
                  {checkingNick === p.nick ? (
                    <div className="cp-check-loading" title={`Проверка... ${checkTimer}с`}>
                      <div className="cp-check-spinner" />
                      <span className="cp-check-timer">{checkTimer}с</span>
                    </div>
                  ) : (
                    <>
                      <button
                        className="cp-btn-check"
                        onClick={() => handleCheck(p.nick)}
                        title="Проверить"
                      >
                        🔍
                      </button>
                      <button
                        className="cp-btn-notes"
                        onClick={() => handleEditNotes(p)}
                        title="Заметки"
                      >
                        📝
                      </button>
                      <button
                        className="cp-btn-delete"
                        onClick={() => handleDelete(p.id)}
                        title="Удалить"
                      >
                        🗑️
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)} title="Добавить закрытого персонажа">
        <Input
          label="Ник персонажа"
          value={addNick}
          onChange={(e) => setAddNick(e.target.value)}
          placeholder="Введите ник"
        />
        <div className="cp-modal-actions">
          <Button variant="ghost" onClick={() => setShowAddModal(false)}>Отмена</Button>
          <Button variant="primary" onClick={handleAdd} disabled={!addNick.trim()}>Добавить</Button>
        </div>
      </Modal>

      <Modal isOpen={showResultModal} onClose={() => setShowResultModal(false)} title="Результат проверки">
        {scanResult && (
          <div className="cp-check-result">
            {scanResult.status === 'opened' ? (
              <>
                <div className="cp-result-opened">
                  <span className="cp-result-icon">✅</span>
                  <span>Персонаж <strong>{scanResult.profile.nick}</strong> доступен для анализа</span>
                </div>
                <div className="cp-result-actions">
                  <Button variant="primary" onClick={() => handleSaveSnapshot(scanResult.profile.nick)}>
                    Сохранить слепок
                  </Button>
                  <Button variant="ghost" onClick={() => setShowResultModal(false)}>Закрыть</Button>
                </div>
              </>
            ) : scanResult.status === 'closed' ? (
              <div className="cp-result-closed">
                <span className="cp-result-icon">🔒</span>
                <span>Персонаж <strong>{scanResult.profile.nick}</strong> всё ещё закрыт</span>
              </div>
            ) : (
              <div className="cp-result-error">
                <span className="cp-result-icon">❌</span>
                <span>Ошибка: {scanResult.error}</span>
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal isOpen={showBatchResults} onClose={() => setShowBatchResults(false)} title="Результаты сканирования" wide>
        <div className="cp-batch-results">
          {scanResults.map((r, i) => (
            <div key={i} className={`cp-batch-item cp-batch-${r.status}`}>
              <span className="cp-batch-icon">
                {r.status === 'opened' ? '✅' : r.status === 'closed' ? '🔒' : '❌'}
              </span>
              <span className="cp-batch-nick">{r.nick}</span>
              <span className="cp-batch-status">
                {r.status === 'opened' ? 'Открылся' : r.status === 'closed' ? 'Закрыт' : 'Ошибка'}
              </span>
            </div>
          ))}
        </div>
        <div className="cp-modal-actions">
          <Button variant="primary" onClick={() => setShowBatchResults(false)}>Закрыть</Button>
        </div>
      </Modal>

      <Modal isOpen={showNotesModal} onClose={() => setShowNotesModal(false)} title={`Заметки — ${editingProfile?.nick}`}>
        <textarea
          className="cp-notes-textarea"
          value={editNotes}
          onChange={(e) => setEditNotes(e.target.value)}
          placeholder="Заметки о персонаже..."
          rows={5}
        />
        <div className="cp-modal-actions">
          <Button variant="ghost" onClick={() => setShowNotesModal(false)}>Отмена</Button>
          <Button variant="primary" onClick={handleSaveNotes}>Сохранить</Button>
        </div>
      </Modal>
    </div>
  );
}
