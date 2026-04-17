import { useMemo, useState } from 'react';
import type { TreasuryOperationData, ClanMemberData } from '../../types/clanInfo';
import { isTalentOperation, isTalentResource, getOriginalOwner } from '../../utils/treasury';
import './TalentAnalytics.css';

interface TalentAnalyticsProps {
  operations: TreasuryOperationData[];
  members?: ClanMemberData[];
}

interface PlayerTalentSummary {
  nick: string;
  resources: Record<string, number>;
  status: 'submitted' | 'not_submitted';
}

type SortDirection = 'asc' | 'desc';

interface SortConfig {
  column: string | null;
  direction: SortDirection;
}

interface GroupConfig {
  key: string;
  name: string;
  resources: { key: string; name: string; shortName?: string }[];
}

const RESOURCE_GROUPS: GroupConfig[] = [
  {
    key: 'universal',
    name: 'Универсальные',
    resources: [
      { key: 'crystal', name: 'Кристаллы истины', shortName: 'Кристаллы' },
      { key: 'treaty_page', name: 'Страница из трактата «Единство клана»', shortName: 'Страницы' },
      { key: 'treaties', name: 'Трактаты I-V', shortName: 'Трактаты I-V' },
      { key: 'token', name: 'Жетон «Времена года»', shortName: 'Жетоны' },
      { key: 'dust', name: 'Кристаллический прах', shortName: 'Прах' },
    ],
  },
  {
    key: 'mystras',
    name: 'Мистрас',
    resources: [
      { key: 'bracelet', name: 'Браслеты джиннов', shortName: 'Браслеты' },
      { key: 'mo_dathar_1', name: 'Мо-датхар альвы благонравной', shortName: 'мо-датхары альвы' },
      { key: 'mo_dathar_2', name: 'Мо-датхар нурида', shortName: 'мо-датхары нурида' },
      { key: 'mo_dathar_3', name: 'Мо-датхар золотой шамсы', shortName: 'мо-датхары шамсы' },
    ],
  },
  {
    key: 'clan_mkk',
    name: 'Клановые + МКК',
    resources: [
      { key: 'battle_cert', name: 'Боевое свидетельство', shortName: 'Боевое' },
      { key: 'giamber', name: 'Гиамбир', shortName: 'Гиамбир' },
      { key: 'eldorill', name: 'Эльдорилл', shortName: 'Эльдорилл' },
      { key: 'gold_habus', name: 'Золотой хабус', shortName: 'Хабус' },
      { key: 'phosphor', name: 'Фосфорическая пыль', shortName: 'Фосфор' },
      { key: 'chain', name: 'Звено цепи Лудьиал', shortName: 'Звено' },
      { key: 'evil_eye', name: 'Злое око', shortName: 'Злое око' },
      { key: 'ether', name: 'Эфирная пыль', shortName: 'Эфир' },
    ],
  },
];

const RESOURCE_KEY_MAP: Record<string, string> = {
  crystal: 'Кристаллы истины',
  treaty_page: 'Страница из трактата «Единство клана»',
  treaties: 'Трактат «Единство клана I»',
  token: 'Жетон «Времена года»',
  dust: 'Кристаллизованный прах',
  bracelet: 'Браслеты джиннов',
  mo_dathar_1: 'Мо-датхар альвы благонравной',
  mo_dathar_2: 'Мо-датхар нурида',
  mo_dathar_3: 'Мо-датхар золотой шамсы',
  battle_cert: 'Боевое свидетельство',
  giamber: 'Гиамбир',
  eldorill: 'Эльдорилл',
  gold_habus: 'Золотой хабус',
  phosphor: 'Фосфорическая пыль',
  chain: 'Звено цепи Лудьиал',
  evil_eye: 'Злое око',
  ether: 'Эфирная пыль',
};

const TREATY_KEYS = ['Трактат «Единство клана I»', 'Трактат «Единство клана II»', 'Трактат «Единство клана III»', 'Трактат «Единство клана IV»', 'Трактат «Единство клана V»'];

type TabKey = 'universal' | 'mystras' | 'clan_mkk';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'universal', label: 'Универсальные' },
  { key: 'mystras', label: 'Мистрас' },
  { key: 'clan_mkk', label: 'Клановые + МКК' },
];

export function TalentAnalytics({ operations, members = [] }: TalentAnalyticsProps) {
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [activeTab, setActiveTab] = useState<TabKey>('universal');
  const [filters, setFilters] = useState({
    search: '',
  });
  const [mainSort, setMainSort] = useState<SortConfig>({ column: 'status', direction: 'asc' });
  const [submittedSort, setSubmittedSort] = useState<SortConfig>({ column: 'nick', direction: 'asc' });
  const [notSubmittedSort, setNotSubmittedSort] = useState<SortConfig>({ column: 'nick', direction: 'asc' });
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  const talentOperations = useMemo(() => {
    return operations.filter(op => {
      if (isTalentOperation(op)) return true;
      if (op.operation_type === 'Возвращено главой' && isTalentResource(op.object_name)) {
        return true;
      }
      return false;
    });
  }, [operations]);

  const playerSummaries = useMemo((): PlayerTalentSummary[] => {
    const byPlayer: Record<string, { resources: Record<string, number> }> = {};

    for (const op of talentOperations) {
      if (op.quantity <= 0) continue;

      const parsed = parseDate(op.date);
      if (!parsed) continue;
      if (parsed.month !== selectedMonth || parsed.year !== selectedYear) continue;

      let owner = op.nick;
      if (op.operation_type === 'Возвращено главой') {
        owner = getOriginalOwner(op, operations);
      }

      if (!byPlayer[owner]) {
        byPlayer[owner] = { resources: {} };
      }
      
      const resName = op.object_name;
      byPlayer[owner].resources[resName] = (byPlayer[owner].resources[resName] || 0) + op.quantity;
    }

    const result: PlayerTalentSummary[] = Object.entries(byPlayer)
      .map(([nick, data]) => ({
        nick,
        resources: data.resources,
        status: 'submitted' as const,
      }));

    const submittedNicks = new Set(result.map(p => p.nick.toLowerCase()));
    for (const m of members) {
      if (!submittedNicks.has(m.nick.toLowerCase())) {
        result.push({
          nick: m.nick,
          resources: {},
          status: 'not_submitted',
        });
      }
    }

    return result.sort((a, b) => {
      const order = { submitted: 0, not_submitted: 1 };
      if (order[a.status] !== order[b.status]) {
        return order[a.status] - order[b.status];
      }
      const aTotal = Object.values(a.resources).reduce((s, v) => s + v, 0);
      const bTotal = Object.values(b.resources).reduce((s, v) => s + v, 0);
      return bTotal - aTotal;
    });
  }, [talentOperations, operations, members, selectedMonth, selectedYear]);

  const monthSummary = useMemo(() => {
    const submittedPlayers = playerSummaries.filter(p => p.status === 'submitted');
    const notSubmittedPlayers = playerSummaries.filter(p => p.status === 'not_submitted');

    return {
      totalPlayers: playerSummaries.length,
      submitted: submittedPlayers.length,
      notSubmitted: notSubmittedPlayers.length,
    };
  }, [playerSummaries]);

  const filteredPlayers = useMemo(() => {
    if (!filters.search) return playerSummaries;
    return playerSummaries.filter(p => 
      p.nick.toLowerCase().includes(filters.search.toLowerCase())
    );
  }, [playerSummaries, filters.search]);

  const submittedPlayers = filteredPlayers.filter(p => p.status === 'submitted');
  const notSubmittedPlayers = filteredPlayers.filter(p => p.status === 'not_submitted');

  const periodLabel = `${MONTHS_RU[selectedMonth]} ${selectedYear}`;

  const handlePrevMonth = () => {
    if (selectedMonth === 1) {
      setSelectedMonth(12);
      setSelectedYear(y => y - 1);
    } else {
      setSelectedMonth(m => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (selectedMonth === 12) {
      setSelectedMonth(1);
      setSelectedYear(y => y + 1);
    } else {
      setSelectedMonth(m => m + 1);
    }
  };

  const getResourceValue = (player: PlayerTalentSummary, resKey: string): number => {
    if (resKey === 'treaties') {
      return TREATY_KEYS.reduce((sum, key) => sum + (player.resources[key] || 0), 0);
    }
    const resName = RESOURCE_KEY_MAP[resKey];
    return player.resources[resName] || 0;
  };

  const getGroupTotals = (players: PlayerTalentSummary[], group: GroupConfig | undefined) => {
    if (!group) return {};

    const totals: Record<string, number> = {};
    for (const res of group.resources) {
      totals[res.key] = players.reduce((sum, p) => sum + getResourceValue(p, res.key), 0);
    }
    return totals;
  };

  const activeGroup = RESOURCE_GROUPS.find(g => g.key === activeTab);
  const groupTotals = getGroupTotals(filteredPlayers, activeGroup);

  const sortedFilteredPlayers = useMemo(() => {
    if (!mainSort.column) return filteredPlayers;
    
    return [...filteredPlayers].sort((a, b) => {
      let cmp = 0;
      switch (mainSort.column) {
        case 'nick':
          cmp = a.nick.localeCompare(b.nick);
          break;
        case 'status':
          cmp = (a.status === 'submitted' ? 0 : 1) - (b.status === 'submitted' ? 0 : 1);
          break;
        default:
          if (mainSort.column.startsWith('res_')) {
            const resKey = mainSort.column.replace('res_', '');
            const aVal = getResourceValue(a, resKey);
            const bVal = getResourceValue(b, resKey);
            cmp = bVal - aVal;
          }
      }
      return mainSort.direction === 'asc' ? cmp : -cmp;
    });
  }, [filteredPlayers, mainSort]);

  const sortedSubmittedPlayers = useMemo(() => {
    if (!submittedSort.column) return submittedPlayers;
    
    return [...submittedPlayers].sort((a, b) => {
      let cmp = 0;
      switch (submittedSort.column) {
        case 'nick':
          cmp = a.nick.localeCompare(b.nick);
          break;
        case 'total':
          const aTotal = Object.values(a.resources).reduce((s, v) => s + v, 0);
          const bTotal = Object.values(b.resources).reduce((s, v) => s + v, 0);
          cmp = bTotal - aTotal;
          break;
      }
      return submittedSort.direction === 'asc' ? cmp : -cmp;
    });
  }, [submittedPlayers, submittedSort]);

  const sortedNotSubmittedPlayers = useMemo(() => {
    if (!notSubmittedSort.column) return notSubmittedPlayers;
    
    return [...notSubmittedPlayers].sort((a, b) => {
      const cmp = a.nick.localeCompare(b.nick);
      return notSubmittedSort.direction === 'asc' ? cmp : -cmp;
    });
  }, [notSubmittedPlayers, notSubmittedSort]);

  const handleSort = (table: 'main' | 'submitted' | 'notSubmitted', column: string) => {
    const setSort = table === 'main' ? setMainSort : table === 'submitted' ? setSubmittedSort : setNotSubmittedSort;
    const currentSort = table === 'main' ? mainSort : table === 'submitted' ? submittedSort : notSubmittedSort;
    
    if (currentSort.column === column) {
      setSort({ column, direction: currentSort.direction === 'asc' ? 'desc' : 'asc' });
    } else {
      setSort({ column, direction: 'desc' });
    }
  };

  const renderSortIcon = (table: 'main' | 'submitted' | 'notSubmitted', column: string) => {
    const currentSort = table === 'main' ? mainSort : table === 'submitted' ? submittedSort : notSubmittedSort;
    if (currentSort.column !== column) return <span className="talent-sort-icon">↕</span>;
    return <span className="talent-sort-icon talent-sort-active">{currentSort.direction === 'asc' ? '↑' : '↓'}</span>;
  };

  const handleCopyTable = async (players: PlayerTalentSummary[], headers: string[]) => {
    if (players.length === 0) return;
    
    const rows = players.map((p, idx) => [
      idx + 1,
      p.nick,
      ...activeGroup?.resources.map(res => getResourceValue(p, res.key) || 0) || []
    ].join('\t')).join('\n');
    
    const text = [headers.join('\t'), rows].join('\n');
    
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus('Скопировано!');
      setTimeout(() => setCopyStatus(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
      setCopyStatus('Ошибка копирования');
      setTimeout(() => setCopyStatus(null), 2000);
    }
  };

  const renderStatusBadge = (status: 'submitted' | 'not_submitted') => {
    if (status === 'not_submitted') {
      return <span className="talent-badge talent-badge-notsubmitted">Не сдавал</span>;
    }
    return <span className="talent-badge talent-badge-submitted">Сдал</span>;
  };

  return (
    <div className="talent-analytics">
      <header className="talent-header">
        <h2 className="talent-title">Ресурсы талантов</h2>
        <div className="talent-period-nav">
          <button onClick={handlePrevMonth}>←</button>
          <span className="talent-period-label">{periodLabel}</span>
          <button onClick={handleNextMonth}>→</button>
        </div>
      </header>

      <div className="talent-kpi">
        <div className="talent-kpi-card">
          <span className="talent-kpi-value">{monthSummary.totalPlayers}</span>
          <span className="talent-kpi-label">Всего</span>
        </div>
        <div className="talent-kpi-card">
          <span className="talent-kpi-value">{submittedPlayers.length}</span>
          <span className="talent-kpi-label">Сдал</span>
        </div>
        <div className="talent-kpi-card talent-kpi-danger">
          <span className="talent-kpi-value">{notSubmittedPlayers.length}</span>
          <span className="talent-kpi-label">Не сдавал</span>
        </div>
      </div>

      <nav className="talent-tabs">
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={`talent-tab ${activeTab === tab.key ? 'talent-tab-active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="talent-filters">
        <input
          type="text"
          className="talent-filter-search"
          placeholder="Поиск по игроку..."
          value={filters.search}
          onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
        />
        {filters.search && (
          <button
            className="talent-filter-clear"
            onClick={() => setFilters({ search: '' })}
          >
            Сбросить
          </button>
        )}
      </div>

      <div className="talent-content">
        <section className="talent-section talent-section-wide">
          <div className="talent-section-header">
            <h3 className="talent-section-title">Сводная — {periodLabel}</h3>
            <div className="talent-section-actions">
              {copyStatus && <span className="talent-copy-status">{copyStatus}</span>}
              <button 
                className="talent-copy-btn" 
                onClick={() => {
                  const headers = ['#', 'Игрок', 'Статус', ...(activeGroup?.resources.map(r => r.shortName || r.name) || [])];
                  handleCopyTable(sortedFilteredPlayers, headers);
                }}
                title="Копировать таблицу"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              </button>
            </div>
          </div>
          <div className="talent-section-totals">
            {activeGroup?.resources.map(res => (
              <span key={res.key} className="talent-total-badge" title={res.name}>
                {res.shortName || res.name}: {groupTotals[res.key] || 0}
              </span>
            ))}
          </div>
          {sortedFilteredPlayers.length > 0 ? (
            <div className="talent-table-wrapper">
              <table className="talent-table talent-table-wide">
                <thead>
                  <tr>
                    <th className="talent-sortable">#</th>
                    <th className="talent-sortable" onClick={() => handleSort('main', 'nick')}>
                      Игрок {renderSortIcon('main', 'nick')}
                    </th>
                    <th className="talent-sortable" onClick={() => handleSort('main', 'status')}>
                      Статус {renderSortIcon('main', 'status')}
                    </th>
                    {activeGroup?.resources.map(res => (
                      <th 
                        key={res.key} 
                        className="talent-sortable" 
                        title={res.name}
                        onClick={() => handleSort('main', 'res_' + res.key)}
                      >
                        {res.shortName || res.name} {renderSortIcon('main', 'res_' + res.key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedFilteredPlayers.map((p, idx) => (
                    <tr key={p.nick}>
                      <td className="talent-rank">{idx + 1}</td>
                      <td className="talent-nick">{p.nick}</td>
                      <td>{renderStatusBadge(p.status)}</td>
                      {activeGroup?.resources.map(res => {
                        const value = getResourceValue(p, res.key);
                        return (
                          <td key={res.key} className={value > 0 ? 'talent-submitted' : ''}>
                            {value > 0 ? value : '-'}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="talent-empty">Нет данных за период</div>
          )}
        </section>

        <section className="talent-section">
          <div className="talent-section-header">
            <h3 className="talent-section-title">
              <span className="talent-status-dot talent-status-submitted" />
              Сдал ({sortedSubmittedPlayers.length})
            </h3>
            {sortedSubmittedPlayers.length > 0 && (
              <div className="talent-section-actions">
                <button 
                  className="talent-copy-btn" 
                  onClick={() => {
                    const headers = ['Игрок', 'Ресурсов'];
                    const rows = sortedSubmittedPlayers.map(p => [p.nick, Object.values(p.resources).reduce((s, v) => s + v, 0)].join('\t')).join('\n');
                    navigator.clipboard.writeText([headers.join('\t'), rows].join('\n')).then(() => { setCopyStatus('Скопировано!'); setTimeout(() => setCopyStatus(null), 2000); });
                  }}
                  title="Копировать таблицу"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                </button>
              </div>
            )}
          </div>
          {sortedSubmittedPlayers.length > 0 ? (
            <div className="talent-table-wrapper">
            <table className="talent-table">
              <thead>
                <tr>
                  <th className="talent-sortable" onClick={() => handleSort('submitted', 'nick')}>
                    Игрок {renderSortIcon('submitted', 'nick')}
                  </th>
                  <th className="talent-sortable" onClick={() => handleSort('submitted', 'total')}>
                    Ресурсов {renderSortIcon('submitted', 'total')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedSubmittedPlayers.map(p => (
                  <tr key={p.nick}>
                    <td className="talent-nick">{p.nick}</td>
                    <td className="talent-submitted">
                      {Object.values(p.resources).reduce((s, v) => s + v, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          ) : (
            <div className="talent-empty">Нет сдавших</div>
          )}
        </section>

        <section className="talent-section">
          <div className="talent-section-header">
            <h3 className="talent-section-title">
              <span className="talent-status-dot talent-status-notsubmitted" />
              Не сдавал ({sortedNotSubmittedPlayers.length})
            </h3>
            {sortedNotSubmittedPlayers.length > 0 && (
              <div className="talent-section-actions">
                <button 
                  className="talent-copy-btn" 
                  onClick={() => {
                    const headers = ['Игрок'];
                    const rows = sortedNotSubmittedPlayers.map(p => p.nick).join('\n');
                    navigator.clipboard.writeText([headers.join('\t'), rows].join('\n')).then(() => { setCopyStatus('Скопировано!'); setTimeout(() => setCopyStatus(null), 2000); });
                  }}
                  title="Копировать таблицу"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                </button>
              </div>
            )}
          </div>
          {sortedNotSubmittedPlayers.length > 0 ? (
            <div className="talent-table-wrapper">
            <table className="talent-table">
              <thead>
                <tr>
                  <th className="talent-sortable" onClick={() => handleSort('notSubmitted', 'nick')}>
                    Игрок {renderSortIcon('notSubmitted', 'nick')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedNotSubmittedPlayers.map(p => (
                  <tr key={p.nick}>
                    <td className="talent-nick">{p.nick}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          ) : (
            <div className="talent-empty">Нет должников</div>
          )}
        </section>
      </div>
    </div>
  );
}

function parseDate(dateStr: string): { day: number; month: number; year: number } | null {
  const match = dateStr.match(/(\d{2})\.(\d{2})\.(\d{4})/);
  if (!match) return null;
  return {
    day: parseInt(match[1], 10),
    month: parseInt(match[2], 10),
    year: parseInt(match[3], 10),
  };
}

const MONTHS_RU = [
  '',
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
];
