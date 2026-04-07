import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { ClanMemberData } from '../../types/clanInfo';
import { getClanMembers, addClanMember, updateClanMember, deleteClanMember } from '../../api/clanInfo';
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

export function ClanMembersTable({ clanId }: ClanMembersTableProps) {
  const navigate = useNavigate();
  const [members, setMembers] = useState<(ClanMemberData & { id?: number })[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState('');
  const [search, setSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingMember, setEditingMember] = useState<(ClanMemberData & { id?: number }) | null>(null);
  const [form, setForm] = useState({ nick: '', game_rank: '', level: 1, profession: '', profession_level: 0, clan_role: '', join_date: '', trial_until: '' });

  useEffect(() => {
    loadMembers();
  }, [clanId]);

  const loadMembers = async () => {
    try {
      const data = await getClanMembers(clanId);
      setMembers(data);
    } catch { /* ignore */ }
    finally { setIsLoading(false); }
  };

  const uniqueRoles = useMemo(() => {
    const roles = new Set(members.map((m) => m.clan_role));
    return Array.from(roles).sort();
  }, [members]);

  const filtered = useMemo(() => {
    return members.filter((m) => {
      if (roleFilter && m.clan_role !== roleFilter) return false;
      if (search && !m.nick.toLowerCase().includes(search.toLowerCase())) return false;
      if (levelFilter && m.level !== parseInt(levelFilter)) return false;
      return true;
    });
  }, [members, roleFilter, search, levelFilter]);

  const handleAdd = async () => {
    if (!form.nick || !form.clan_role || !form.level) return;
    try {
      const newMember = await addClanMember(clanId, form);
      setMembers((prev) => [...prev, newMember]);
      setShowAddModal(false);
      setForm({ nick: '', game_rank: '', level: 1, profession: '', profession_level: 0, clan_role: '', join_date: '', trial_until: '' });
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

  const handleDelete = async (member: ClanMemberData & { id?: number }) => {
    if (!member.id) return;
    if (!confirm(`Удалить ${member.nick} из клана?`)) return;
    try {
      await deleteClanMember(clanId, member.id);
      setMembers((prev) => prev.filter((m) => m.id !== member.id));
    } catch { /* ignore */ }
  };

  const handleAnalyze = (nick: string) => {
    const url = `https://w1.dwar.ru/user_info.php?nick=${encodeURIComponent(nick)}`;
    navigate(`/?analyze=${encodeURIComponent(url)}`);
  };

  const openEdit = (m: ClanMemberData & { id?: number }) => {
    setEditingMember(m);
    setForm({
      nick: m.nick,
      game_rank: m.game_rank,
      level: m.level,
      profession: m.profession,
      profession_level: m.profession_level,
      clan_role: m.clan_role,
      join_date: m.join_date,
      trial_until: m.trial_until,
    });
  };

  if (isLoading) return <LoadingSpinner />;
  if (members.length === 0) return <p className="cm-empty">Участники не найдены</p>;

  const formFields = (
    <>
      <Input label="Ник" value={form.nick} onChange={(e) => setForm({ ...form, nick: e.target.value })} required />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <div>
          <label className="cm-form-label">Ранг</label>
          <select className="cm-form-select" value={form.game_rank} onChange={(e) => setForm({ ...form, game_rank: e.target.value })}>
            <option value="">—</option>
            {GAME_RANKS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <Input label="Уровень" type="number" value={form.level} onChange={(e) => setForm({ ...form, level: parseInt(e.target.value) || 1 })} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <div>
          <label className="cm-form-label">Профессия</label>
          <select className="cm-form-select" value={form.profession} onChange={(e) => setForm({ ...form, profession: e.target.value })}>
            <option value="">—</option>
            {PROFESSIONS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        {form.profession && <Input label="Ур. профессии" type="number" value={form.profession_level} onChange={(e) => setForm({ ...form, profession_level: parseInt(e.target.value) || 0 })} />}
      </div>
      <div>
        <label className="cm-form-label">Роль в клане</label>
        <select className="cm-form-select" value={form.clan_role} onChange={(e) => setForm({ ...form, clan_role: e.target.value })} required>
          <option value="">Выберите</option>
          {CLAN_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <Input label="Дата вступления" value={form.join_date} onChange={(e) => setForm({ ...form, join_date: e.target.value })} placeholder="ДД.ММ.ГГГГ" />
        <Input label="Исп. срок до" value={form.trial_until} onChange={(e) => setForm({ ...form, trial_until: e.target.value })} placeholder="ДД.ММ.ГГГГ" />
      </div>
    </>
  );

  return (
    <div className="clan-members">
      <div className="cm-toolbar">
        <div className="cm-filters">
          <input className="cm-search" placeholder="Поиск по нику..." value={search} onChange={(e) => setSearch(e.target.value)} />
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
        <Button variant="primary" onClick={() => { setShowAddModal(true); setForm({ nick: '', game_rank: '', level: 1, profession: '', profession_level: 0, clan_role: '', join_date: '', trial_until: '' }); }}>
          + Добавить
        </Button>
      </div>

      <table className="cm-table">
        <thead>
          <tr>
            <th>Ник</th>
            <th>Роль</th>
            <th>Вступил</th>
            <th style={{ width: '110px' }}></th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((m, i) => (
            <tr key={m.id || i} className={m.trial_until ? 'cm-trial' : ''}>
              <td className="cm-nick">
                {m.profession && (
                  <span className="cm-prof" title={`${m.profession}: ${m.profession_level}`}>{m.profession[0]}</span>
                )}
                <span>{m.nick}</span>
                <span className="cm-level">[{m.level}]</span>
                {m.game_rank && <span className="cm-game-rank">{m.game_rank}</span>}
              </td>
              <td className="cm-role">{m.clan_role}</td>
              <td className="cm-join">
                {m.trial_until ? <span className="cm-trial-badge">Исп. до {m.trial_until}</span> : m.join_date}
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
    </div>
  );
}
