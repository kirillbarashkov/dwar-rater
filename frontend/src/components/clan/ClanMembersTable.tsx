import { useState, useEffect, useMemo, useCallback } from 'react';
import type { ClanMemberData, LeftMemberData } from '../../types/clanInfo';
import type { ClanInfoData } from '../../utils/parseMembers';
import { getClanMembers, addClanMember, updateClanMember, deleteClanMember, importClanMembers, getLeftMembers } from '../../api/clanInfo';
import { useAuth } from '../../hooks/useAuth';
import { parseMembersFile } from '../../utils/parseMembers';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Modal } from '../ui/Modal';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import './ClanMembersTable.css';

interface ClanMembersTableProps {
  clanId: number;
}

const CLAN_ROLES = [
  'Глава Ордена', 'Зам. Главы', 'Совесть', 'Рыцарь Ордена', 'Леди Ордена',
  'ГардеМаринкА', 'Фея на метле', 'Лентяй', 'Пельмешка', 'Dead\'ok',
  'Воевода', '9-ть жЫзней)', 'УлитЫчка)', 'РудольФ', 'Сосиска',
];

const GAME_RANKS = [
  'Герой', 'Властелин боя', 'Вершитель', 'Магистр войны', 'Повелитель',
  'Полководец', 'Легендарный завоеватель', 'Военный эксперт', 'Мастер войны',
  'Элитный воин', 'Гладиатор', 'Чемпион', 'Избранник богов', 'Триумфатор', 'Высший магистр',
];

const PROFESSIONS = ['Взломщик', 'Палач', 'Целитель'];

const ICONS = ['⚔️', '🗡️', '🛡️', '⚖️', '🔥', '❄️', '⚡', '🌙', '☀️', '💀', '👑', '🎭', '🎯', '💎', '🔮', '🩸', '🪓', '🏹', '🪄', '⚓', '🪁', '🪃', '🎮', ''];

const PROFESSION_COLORS: Record<string, string> = {
  'Палач': '#b91c1c',
  'Целитель': '#15803d',
  'Взломщик': '#333333',
};

export function ClanMembersTable({ clanId }: ClanMembersTableProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [members, setMembers] = useState<(ClanMemberData & { id?: number })[]>([]);
  const [leftMembers, setLeftMembers] = useState<LeftMemberData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState('');
  const [search, setSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingMember, setEditingMember] = useState<(ClanMemberData & { id?: number }) | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importedMembers, setImportedMembers] = useState<Partial<ClanMemberData>[]>([]);
  const [importedClanInfo, setImportedClanInfo] = useState<ClanInfoData | undefined>();
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [importSkipped, setImportSkipped] = useState(0);
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [form, setForm] = useState({ nick: '', icon: '', game_rank: '', level: 1, profession: '', profession_level: 0, clan_role: '', join_date: '', trial_until: '' });
  const [sortConfig, setSortConfig] = useState<{ key: string; dir: 'asc' | 'desc' }>({ key: 'nick', dir: 'asc' });
  const [deletingMember, setDeletingMember] = useState<(ClanMemberData & { id?: number }) | null>(null);
  const [deleteReason, setDeleteReason] = useState('');
  const [leftSearch, setLeftSearch] = useState('');
  const [leftDateFilter, setLeftDateFilter] = useState('');
  const [leftReasonFilter, setLeftReasonFilter] = useState('');

  useEffect(() => {
    loadMembers();
    loadLeftMembers();
  }, [clanId]);

  const loadMembers = async () => {
    try {
      const data = await getClanMembers(clanId);
      setMembers(data);
    } catch { /* ignore */ }
    finally { setIsLoading(false); }
  };

  const loadLeftMembers = async () => {
    try {
      const data = await getLeftMembers(clanId);
      setLeftMembers(data);
    } catch { /* ignore */ }
  };

  const uniqueRoles = useMemo(() => {
    const roles = new Set(members.map((m) => m.clan_role));
    return Array.from(roles).sort();
  }, [members]);

  const filtered = useMemo(() => {
    let result = members.filter((m) => {
      if (roleFilter && m.clan_role !== roleFilter) return false;
      if (search && !m.nick.toLowerCase().includes(search.toLowerCase())) return false;
      if (levelFilter && m.level !== parseInt(levelFilter)) return false;
      return true;
    });

if (sortConfig.key) {
      result = [...result].sort((a, b) => {
        const aVal = a[sortConfig.key as keyof ClanMemberData];
        const bVal = b[sortConfig.key as keyof ClanMemberData];
        if (aVal == null || bVal == null) return 0;
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return sortConfig.dir === 'asc' ? aVal - bVal : bVal - aVal;
        }
        // Handle date sorting (DD.MM.YYYY format)
        if (sortConfig.key === 'join_date' && aVal && bVal) {
          const parseDate = (d: string) => {
            const parts = d.split('.');
            if (parts.length === 3) {
              return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
            }
            return new Date(0);
          };
          const dateA = parseDate(String(aVal));
          const dateB = parseDate(String(bVal));
          return sortConfig.dir === 'asc' ? dateA.getTime() - dateB.getTime() : dateB.getTime() - dateA.getTime();
        }
        const aStr = String(aVal).toLowerCase();
        const bStr = String(bVal).toLowerCase();
        return sortConfig.dir === 'asc' ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
      });
    }

    return result;
  }, [members, roleFilter, search, levelFilter, sortConfig]);

  const filteredLeft = useMemo(() => {
    return leftMembers.filter((m) => {
      if (leftSearch && !m.nick.toLowerCase().includes(leftSearch.toLowerCase())) return false;
      if (leftDateFilter && m.left_date !== leftDateFilter) return false;
      if (leftReasonFilter && m.leave_reason !== leftReasonFilter) return false;
      return true;
    });
  }, [leftMembers, leftSearch, leftDateFilter, leftReasonFilter]);

  const uniqueLeftDates = useMemo(() => {
    const dates = new Set(leftMembers.map((m) => m.left_date));
    return Array.from(dates).sort().reverse();
  }, [leftMembers]);

  const uniqueLeftReasons = useMemo(() => {
    const reasons = new Set(leftMembers.map((m) => m.leave_reason).filter(Boolean));
    return Array.from(reasons).sort();
  }, [leftMembers]);

  const handleSort = (key: string) => {
    setSortConfig((prev) => ({
      key,
      dir: prev.key === key && prev.dir === 'asc' ? 'desc' : 'asc',
    }));
  };

  const handleAdd = async () => {
    if (!form.nick || !form.clan_role || !form.level) return;
    try {
      const newMember = await addClanMember(clanId, form);
      setMembers((prev) => [...prev, newMember]);
      setShowAddModal(false);
      setForm({ nick: '', icon: '', game_rank: '', level: 1, profession: '', profession_level: 0, clan_role: '', join_date: '', trial_until: '' });
    } catch { /* ignore */ }
  };

  const handleEdit = async () => {
    if (!editingMember?.id) return;
    try {
      const updated = await updateClanMember(clanId, editingMember.id, form);
      setMembers((prev) => prev.map((m) => m.id === editingMember.id ? { ...m, ...updated } : m));
      setEditingMember(null);
    } catch { /* ignore */ }
  };

  const handleDelete = (member: ClanMemberData & { id?: number }) => {
    if (!member.id) return;
    setDeletingMember(member);
    setDeleteReason('');
  };

  const confirmDelete = async () => {
    if (!deletingMember?.id) return;
    try {
      const today = new Date().toLocaleDateString('ru-RU');
      await deleteClanMember(clanId, deletingMember.id, deleteReason, today);
      setMembers((prev) => prev.filter((m) => m.id !== deletingMember.id));
      loadLeftMembers();
      setDeletingMember(null);
      setDeleteReason('');
    } catch { /* ignore */ }
  };

const handleAnalyze = (nick: string) => {
    const url = `https://w1.dwar.ru/user_info.php?nick=${encodeURIComponent(nick)}`;
    sessionStorage.setItem('pending_analyze', url);
    window.location.href = '/';
  };

  const openEdit = (m: ClanMemberData & { id?: number }) => {
    setEditingMember(m);
    setForm({
      nick: m.nick,
      icon: m.icon || '',
      game_rank: m.game_rank,
      level: m.level,
      profession: m.profession,
      profession_level: m.profession_level,
      clan_role: m.clan_role,
      join_date: m.join_date,
      trial_until: m.trial_until,
    });
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    const file = files.find(f => f.name.endsWith('.txt') || f.name.endsWith('.csv') || f.name.endsWith('.json') || f.name.endsWith('.md'));
    
    if (!file) {
      setImportErrors(['Поддерживаются только файлы .txt, .csv, .json, .md']);
      return;
    }

    try {
      const text = await file.text();
      const { members: parsed, clanInfo, errors } = parseMembersFile(text);
      setImportedMembers(parsed);
      setImportedClanInfo(clanInfo);
      setImportErrors(errors);
    } catch (err) {
      setImportErrors([`Ошибка чтения файла: ${err}`]);
    }
  }, []);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const { members: parsed, clanInfo, errors } = parseMembersFile(text);
      setImportedMembers(parsed);
      setImportedClanInfo(clanInfo);
      setImportErrors(errors);
    } catch (err) {
      setImportErrors([`Ошибка чтения файла: ${err}`]);
    }
  }, []);

  const handleImportConfirm = async () => {
    if (importedMembers.length === 0) return;
    setIsImporting(true);
    try {
      const result = await importClanMembers(clanId, importedMembers, overwriteExisting, importedClanInfo);
      if (result.success > 0) {
        loadMembers();
        setShowImportModal(false);
        setImportedMembers([]);
        setImportedClanInfo(undefined);
        setImportErrors([]);
        setOverwriteExisting(false);
      }
      if (result.skipped > 0) {
        setImportSkipped(result.skipped);
      }
      if (result.errors.length > 0) {
        setImportErrors(result.errors);
      }
    } catch (err) {
      setImportErrors([`Ошибка импорта: ${err}`]);
    } finally {
      setIsImporting(false);
    }
  };

  const openImportModal = () => {
    setImportedMembers([]);
    setImportedClanInfo(undefined);
    setImportErrors([]);
    setImportSkipped(0);
    setOverwriteExisting(false);
    setShowImportModal(true);
  };

  if (isLoading) return <LoadingSpinner />;

  const formFields = (
    <>
      <div className="cm-form-row">
        <div className="cm-icon-select">
          <label className="cm-form-label">Иконка</label>
          <select className="cm-form-select" value={form.icon || ''} onChange={(e) => setForm({ ...form, icon: e.target.value })}>
            <option value="">—</option>
            {ICONS.slice(0, -1).map((icon) => (
              <option key={icon} value={icon}>{icon}</option>
            ))}
          </select>
        </div>
        <div className="cm-nick-input">
          <Input label="Ник" value={form.nick} onChange={(e) => setForm({ ...form, nick: e.target.value })} required />
        </div>
      </div>
      <div className="cm-form-grid">
        <div>
          <label className="cm-form-label">Ранг</label>
          <select className="cm-form-select" value={form.game_rank} onChange={(e) => setForm({ ...form, game_rank: e.target.value })}>
            <option value="">—</option>
            {GAME_RANKS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <Input label="Уровень" type="number" value={form.level} onChange={(e) => setForm({ ...form, level: parseInt(e.target.value) || 1 })} />
      </div>
      <div className="cm-form-grid">
        <div>
          <label className="cm-form-label">Профессия</label>
          <select className="cm-form-select" value={form.profession} onChange={(e) => setForm({ ...form, profession: e.target.value })}>
            <option value="">—</option>
            {PROFESSIONS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        {form.profession && <Input label="Ур." type="number" value={form.profession_level} onChange={(e) => setForm({ ...form, profession_level: parseInt(e.target.value) || 0 })} />}
      </div>
      <div>
        <label className="cm-form-label">Роль в клане</label>
        <select className="cm-form-select" value={form.clan_role} onChange={(e) => setForm({ ...form, clan_role: e.target.value })} required>
          <option value="">Выберите</option>
          {CLAN_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>
      <div className="cm-form-grid">
        <Input label="Вступил" value={form.join_date} onChange={(e) => setForm({ ...form, join_date: e.target.value })} placeholder="ДД.ММ.ГГГГ" />
        <Input label="Исп. до" value={form.trial_until} onChange={(e) => setForm({ ...form, trial_until: e.target.value })} placeholder="ДД.ММ.ГГГГ" />
      </div>
    </>
  );

  return (
    <div className="clan-members">
      <div className="cm-toolbar">
<div className="cm-filters">
          <div className="cm-search-wrapper">
            <input className="cm-search" placeholder="Поиск по нику..." value={search} onChange={(e) => setSearch(e.target.value)} />
            {search && <button className="cm-search-clear" onClick={() => setSearch('')}>×</button>}
          </div>
          <select className="cm-role-filter" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">Все звания ({members.length})</option>
            {uniqueRoles.map((role) => (
              <option key={role} value={role}>{role} ({members.filter((m) => m.clan_role === role).length})</option>
            ))}
          </select>
          <div className="cm-level-filter">
            <select className="cm-role-filter" value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)}>
              <option value="">Все уровни</option>
              {Array.from(new Set(members.map((m) => m.level))).sort((a, b) => a - b).map((lvl) => (
                <option key={lvl} value={lvl}>{lvl} ({members.filter((m) => m.level === lvl).length})</option>
              ))}
            </select>
          </div>
        </div>
        <Button variant="primary" onClick={() => { setShowAddModal(true); setForm({ nick: '', icon: '', game_rank: '', level: 1, profession: '', profession_level: 0, clan_role: '', join_date: '', trial_until: '' }); }}>
          + Добавить
        </Button>
        {isAdmin && (
          <Button variant="secondary" onClick={openImportModal}>
            Импорт
          </Button>
        )}
      </div>

      <table className="cm-table">
        <thead>
          <tr>
            <th className="cm-number">#</th>
            <th className="cm-sortable" onClick={() => handleSort('nick')}>
              Ник {sortConfig.key === 'nick' && (sortConfig.dir === 'asc' ? '↑' : '↓')}
            </th>
            <th className="cm-sortable" onClick={() => handleSort('clan_role')}>
              Клановое звание {sortConfig.key === 'clan_role' && (sortConfig.dir === 'asc' ? '↑' : '↓')}
            </th>
            <th className="cm-sortable" onClick={() => handleSort('join_date')}>
              Вступил {sortConfig.key === 'join_date' && (sortConfig.dir === 'asc' ? '↑' : '↓')}
            </th>
            <th className="cm-actions-header">Действия</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((m, i) => (
            <tr key={m.id || i} className={m.trial_until ? 'cm-trial' : ''}>
              <td className="cm-number">{i + 1}</td>
              <td className="cm-nick">
                {m.icon && <span className="cm-icon">{m.icon}</span>}
                <span>{m.nick}</span>
                <span className="cm-level">[{m.level}]</span>
                {m.game_rank && <span className="cm-game-rank">{m.game_rank}</span>}
                {m.profession && (
                  <span className="cm-prof" style={{ '--prof-color': PROFESSION_COLORS[m.profession] || 'var(--bg-secondary)' } as React.CSSProperties} title={`${m.profession}: ${m.profession_level}`}>
                    {m.profession}: {m.profession_level}
                  </span>
                )}
              </td>
              <td className="cm-role">{m.clan_role}</td>
              <td className="cm-join">
                {m.join_date && <span>{m.join_date}</span>}
                {m.trial_until && <span className="cm-trial-badge">Исп. до {m.trial_until}</span>}
              </td>
              <td className="cm-actions">
                <button className="cm-btn-analyze" onClick={() => handleAnalyze(m.nick)} title="Анализировать">📊</button>
                <button className="cm-btn-edit" onClick={() => openEdit(m)} title="Редактировать">✏️</button>
                <button className="cm-btn-del" onClick={() => handleDelete(m)} title="Удалить">🗑️</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {filtered.length === 0 && <p className="cm-no-results">Никого не найдено</p>}

      {leftMembers.length > 0 && (
        <div className="cm-left-section">
          <h3 className="cm-left-title">Выбывшие участники ({filteredLeft.length})</h3>
          <div className="cm-filters cm-left-filters">
            <input
              className="cm-search"
              placeholder="Поиск по нику..."
              value={leftSearch}
              onChange={(e) => setLeftSearch(e.target.value)}
            />
            <select
              className="cm-role-filter"
              value={leftDateFilter}
              onChange={(e) => setLeftDateFilter(e.target.value)}
            >
              <option value="">Все даты</option>
              {uniqueLeftDates.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
            <select
              className="cm-role-filter"
              value={leftReasonFilter}
              onChange={(e) => setLeftReasonFilter(e.target.value)}
            >
              <option value="">Все причины</option>
              {uniqueLeftReasons.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            {leftSearch || leftDateFilter || leftReasonFilter ? (
              <button className="cm-search-clear" onClick={() => { setLeftSearch(''); setLeftDateFilter(''); setLeftReasonFilter(''); }}>×</button>
            ) : null}
          </div>
          <table className="cm-table">
            <thead>
              <tr>
                <th className="cm-number">#</th>
                <th className="cm-sortable">Ник</th>
                <th className="cm-sortable">Дата ухода</th>
                <th className="cm-sortable">Причина ухода</th>
                <th className="cm-actions-header">Действия</th>
              </tr>
            </thead>
            <tbody>
              {filteredLeft.map((m, i) => (
                <tr key={m.id}>
                  <td className="cm-number">{i + 1}</td>
                  <td className="cm-nick">
                    {m.icon && <span className="cm-icon">{m.icon}</span>}
                    <span>{m.nick}</span>
                    <span className="cm-level">[{m.level}]</span>
                  </td>
                  <td className="cm-join">{m.left_date}</td>
                  <td className="cm-reason">{m.leave_reason || '—'}</td>
                  <td className="cm-actions">
                    <button className="cm-btn-analyze" onClick={() => handleAnalyze(m.nick)} title="Анализировать">📊</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredLeft.length === 0 && <p className="cm-no-results">Никого не найдено</p>}
        </div>
      )}

      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)} title="Добавить участника">
        {formFields}
        <div className="cm-modal-actions">
          <Button variant="ghost" onClick={() => setShowAddModal(false)}>Отмена</Button>
          <Button variant="primary" onClick={handleAdd}>Добавить</Button>
        </div>
      </Modal>

      <Modal isOpen={!!editingMember} onClose={() => setEditingMember(null)} title="Редактировать участника">
        {formFields}
        <div className="cm-modal-actions">
          <Button variant="ghost" onClick={() => setEditingMember(null)}>Отмена</Button>
          <Button variant="primary" onClick={handleEdit}>Сохранить</Button>
        </div>
      </Modal>

      <Modal isOpen={showImportModal} onClose={() => setShowImportModal(false)} title="Импорт участников" wide>
        <div className="cm-import">
          <div
            className={`cm-dropzone ${isDragging ? 'dragging' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="cm-dropzone-content">
              <span className="cm-dropzone-icon">📁</span>
              <p>Перетащите файл сюда</p>
              <p className="cm-dropzone-hint">или</p>
              <label className="cm-file-btn">
                Выберите файл
                <input type="file" accept=".txt,.csv,.json,.md" onChange={handleFileSelect} style={{ display: 'none' }} />
              </label>
            </div>
          </div>

          {importErrors.length > 0 && (
            <div className="cm-import-errors">
              {importErrors.map((err, i) => (
                <p key={i} className="cm-import-error">{err}</p>
              ))}
            </div>
          )}

          {importedMembers.length > 0 && (
            <div className="cm-import-preview">
              <h4>Найдено участников: {importedMembers.length}</h4>
              <div className="cm-import-list">
                {importedMembers.slice(0, 10).map((m, i) => (
                  <div key={i} className="cm-import-item">
                    <span className="cm-import-nick">{m.nick}</span>
                    <span className="cm-import-level">[{m.level}]</span>
                    <span className="cm-import-role">{m.clan_role}</span>
                  </div>
                ))}
                {importedMembers.length > 10 && (
                  <p className="cm-import-more">...и ещё {importedMembers.length - 10}</p>
                )}
              </div>
              <label className="cm-import-overwrite">
                <input
                  type="checkbox"
                  checked={overwriteExisting}
                  onChange={(e) => setOverwriteExisting(e.target.checked)}
                />
                Перезаписать существующие данные
              </label>
              {importSkipped > 0 && (
                <p className="cm-import-skipped">Пропущено дубликатов: {importSkipped}</p>
              )}
            </div>
          )}
        </div>

        <div className="cm-modal-actions">
          <Button variant="ghost" onClick={() => setShowImportModal(false)}>Отмена</Button>
          <Button variant="primary" onClick={handleImportConfirm} disabled={importedMembers.length === 0 || isImporting}>
            {isImporting ? 'Импорт...' : `Импортировать (${importedMembers.length})`}
          </Button>
        </div>
      </Modal>

      <Modal isOpen={!!deletingMember} onClose={() => setDeletingMember(null)} title="Удалить участника">
        <p>Удалить {deletingMember?.nick} из клана?</p>
        <div className="cm-form-group">
          <label className="cm-form-label">Причина ухода</label>
          <select className="cm-form-select" value={deleteReason} onChange={(e) => setDeleteReason(e.target.value)}>
            <option value="">Выберите причину</option>
            <option value="Вышел сам">Вышел сам</option>
            <option value="Исключен">Исключен</option>
            <option value="Переведен в другой клан">Переведен в другой клан</option>
            <option value="Не активен">Не активен</option>
            <option value="Другое">Другое</option>
          </select>
        </div>
        <div className="cm-modal-actions">
          <Button variant="ghost" onClick={() => setDeletingMember(null)}>Отмена</Button>
          <Button variant="primary" onClick={confirmDelete}>Подтвердить</Button>
        </div>
      </Modal>
    </div>
  );
}
