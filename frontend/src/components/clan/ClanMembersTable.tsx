import { useState, useEffect, useMemo } from 'react';
import type { ClanMemberData } from '../../types/clanInfo';
import { getClanMembers } from '../../api/clanInfo';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import './ClanMembersTable.css';

interface ClanMembersTableProps {
  clanId: number;
}

const CLAN_ROLES_ORDER = [
  'Глава Ордена', 'Зам. Главы', 'Совесть', 'Рыцарь Ордена', 'Леди Ордена',
  'ГардеМаринкА', 'Фея на метле', 'Лентяй', 'Пельмешка', 'Dead\'ok',
  'Воевода', '9-ть жЫзней)', 'УлитЫчка)', 'РудольФ', 'Сосиска',
];

export function ClanMembersTable({ clanId }: ClanMembersTableProps) {
  const [members, setMembers] = useState<ClanMemberData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    getClanMembers(clanId)
      .then(setMembers)
      .catch(() => setMembers([]))
      .finally(() => setIsLoading(false));
  }, [clanId]);

  const uniqueRoles = useMemo(() => {
    const roles = new Set(members.map((m) => m.clan_role));
    return Array.from(roles).sort((a, b) => {
      const ai = CLAN_ROLES_ORDER.indexOf(a);
      const bi = CLAN_ROLES_ORDER.indexOf(b);
      if (ai === -1 && bi === -1) return a.localeCompare(b);
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    });
  }, [members]);

  const filtered = useMemo(() => {
    return members.filter((m) => {
      if (roleFilter && m.clan_role !== roleFilter) return false;
      if (search && !m.nick.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [members, roleFilter, search]);

  if (isLoading) return <LoadingSpinner />;
  if (members.length === 0) return <p className="cm-empty">Участники не найдены</p>;

  return (
    <div className="clan-members">
      <div className="cm-filters">
        <input
          className="cm-search"
          placeholder="Поиск по нику..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="cm-role-filter"
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
        >
          <option value="">Все звания ({members.length})</option>
          {uniqueRoles.map((role) => (
            <option key={role} value={role}>
              {role} ({members.filter((m) => m.clan_role === role).length})
            </option>
          ))}
        </select>
      </div>

      <table className="cm-table">
        <thead>
          <tr>
            <th>Ник</th>
            <th>Звание</th>
            <th>Роль в клане</th>
            <th>Вступил</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((m, i) => (
            <tr key={i} className={m.trial_until ? 'cm-trial' : ''}>
              <td className="cm-nick">
                {m.profession && (
                  <span className="cm-prof" title={`${m.profession}: ${m.profession_level}`}>
                    {m.profession[0]}
                  </span>
                )}
                <span>{m.nick}</span>
                <span className="cm-level">[{m.level}]</span>
                {m.game_rank && <span className="cm-game-rank">{m.game_rank}</span>}
              </td>
              <td className="cm-role">{m.clan_role}</td>
              <td className="cm-join">
                {m.trial_until ? (
                  <span className="cm-trial-badge">Исп. до {m.trial_until}</span>
                ) : (
                  m.join_date
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {filtered.length === 0 && (
        <p className="cm-no-results">Никого не найдено</p>
      )}
    </div>
  );
}
