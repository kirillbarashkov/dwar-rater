import { useMemo, useState } from 'react';
import type { TreasuryOperationData, ClanMemberData } from '../../types/clanInfo';
import { isTalentOperation, isTalentResource, getOriginalOwner, TALENT_RESOURCE_GROUPS } from '../../utils/treasury';
import './TalentAnalytics.css';

interface TalentAnalyticsProps {
  operations: TreasuryOperationData[];
  members?: ClanMemberData[];
}

interface PlayerTalentSummary {
  nick: string;
  totalContributed: number;
  resourceCount: number;
  resources: Record<string, number>;
  status: 'submitted' | 'not_submitted';
}

interface MonthSummary {
  players: PlayerTalentSummary[];
  totalCollected: number;
  expectedByNorm: number;
  expectedByAvg: number;
}

const NORM_PER_PLAYER = 1;

export function TalentAnalytics({ operations, members = [] }: TalentAnalyticsProps) {
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [filters, setFilters] = useState({
    search: '',
    group: '',
  });

  const allResources = useMemo(() => {
    const resources = new Set<string>();
    for (const group of TALENT_RESOURCE_GROUPS) {
      for (const res of group.resources) {
        resources.add(res);
      }
    }
    return Array.from(resources);
  }, []);

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
    const byPlayer: Record<string, { total: number; resources: Record<string, number> }> = {};

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
        byPlayer[owner] = { total: 0, resources: {} };
      }
      byPlayer[owner].total += op.quantity;
      byPlayer[owner].resources[op.object_name] = (byPlayer[owner].resources[op.object_name] || 0) + op.quantity;
    }

    const result: PlayerTalentSummary[] = Object.entries(byPlayer)
      .map(([nick, data]) => ({
        nick,
        totalContributed: data.total,
        resourceCount: Object.keys(data.resources).length,
        resources: data.resources,
        status: 'submitted' as const,
      }));

    const submittedNicks = new Set(result.map(p => p.nick.toLowerCase()));
    for (const m of members) {
      if (!submittedNicks.has(m.nick.toLowerCase())) {
        result.push({
          nick: m.nick,
          totalContributed: 0,
          resourceCount: 0,
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
      return b.totalContributed - a.totalContributed;
    });
  }, [talentOperations, operations, selectedMonth, selectedYear]);

  const monthSummary = useMemo((): MonthSummary | null => {
    const totalCollected = playerSummaries.reduce((sum, p) => sum + p.totalContributed, 0);
    const playerCount = playerSummaries.length;
    const expectedByNorm = playerCount * NORM_PER_PLAYER * allResources.length;
    const avgContribution = playerCount > 0 ? totalCollected / playerCount : 0;
    const expectedByAvg = playerCount * avgContribution;

    return {
      players: playerSummaries,
      totalCollected,
      expectedByNorm,
      expectedByAvg,
    };
  }, [playerSummaries, allResources.length]);

  const filteredPlayers = useMemo(() => {
    if (!monthSummary) return [];
    
    return monthSummary.players.filter(p => {
      if (filters.search && !p.nick.toLowerCase().includes(filters.search.toLowerCase())) {
        return false;
      }
      if (filters.group) {
        const group = TALENT_RESOURCE_GROUPS.find(g => g.name === filters.group);
        if (group) {
          const hasResourceInGroup = Object.keys(p.resources).some(r => group.resources.includes(r));
          if (!hasResourceInGroup && p.status === 'submitted') {
            return false;
          }
        }
      }
      return true;
    });
  }, [monthSummary, filters]);

  const submittedPlayers = filteredPlayers.filter(p => p.status === 'submitted');
  const notSubmittedPlayers = filteredPlayers.filter(p => p.status === 'not_submitted');

  const periodLabel = monthSummary
    ? `${MONTHS_RU[selectedMonth]} ${selectedYear}`
    : '';

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

  const renderStatusBadge = (summary: PlayerTalentSummary) => {
    if (summary.status === 'not_submitted') {
      return <span className="talent-badge talent-badge-notsubmitted">Не сдавал</span>;
    }
    return <span className="talent-badge talent-badge-submitted">Сдал</span>;
  };

  const uniqueGroups = TALENT_RESOURCE_GROUPS.map(g => g.name);

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

      {monthSummary && (
        <>
          <div className="talent-kpi">
            <div className="talent-kpi-card">
              <span className="talent-kpi-value">{monthSummary.totalCollected.toLocaleString()}</span>
              <span className="talent-kpi-label">Сдано</span>
            </div>
            <div className="talent-kpi-card">
              <span className="talent-kpi-value">{monthSummary.expectedByNorm.toLocaleString()}</span>
              <span className="talent-kpi-label">План по норме</span>
            </div>
            <div className="talent-kpi-card">
              <span className="talent-kpi-value">{monthSummary.expectedByAvg > 0 ? monthSummary.expectedByAvg.toFixed(0) : 0}</span>
              <span className="talent-kpi-label">План по среднему</span>
            </div>
          </div>

          <div className="talent-kpi talent-kpi-row2">
            <div className="talent-kpi-card">
              <span className="talent-kpi-value">{filteredPlayers.length}</span>
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

          <div className="talent-filters">
            <input
              type="text"
              className="talent-filter-search"
              placeholder="Поиск по игроку..."
              value={filters.search}
              onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
            />
            <select
              value={filters.group}
              onChange={e => setFilters(f => ({ ...f, group: e.target.value }))}
            >
              <option value="">Все группы</option>
              {uniqueGroups.map(g => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
            {(filters.search || filters.group) && (
              <button
                className="talent-filter-clear"
                onClick={() => setFilters({ search: '', group: '' })}
              >
                Сбросить
              </button>
            )}
          </div>

          <div className="talent-shortlists">
            <section className="talent-section talent-section-wide">
              <h3 className="talent-section-title">Сводная — {periodLabel}</h3>
              {filteredPlayers.length > 0 ? (
                <div className="talent-table-wrapper">
                  <table className="talent-table talent-table-wide">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Игрок</th>
                        <th>Статус</th>
                        {TALENT_RESOURCE_GROUPS.map(group => (
                          group.resources.map(resource => (
                            <th key={resource} title={resource}>{resource.length > 12 ? resource.slice(0, 12) + '...' : resource}</th>
                          ))
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredPlayers.map((p, idx) => (
                        <tr key={p.nick}>
                          <td className="talent-rank">{idx + 1}</td>
                          <td className="talent-nick">{p.nick}</td>
                          <td>{renderStatusBadge(p)}</td>
                          {TALENT_RESOURCE_GROUPS.map(group => (
                            group.resources.map(resource => (
                              <td key={resource} className={p.resources[resource] ? 'talent-submitted' : ''}>
                                {p.resources[resource] || '-'}
                              </td>
                            ))
                          ))}
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
              <h3 className="talent-section-title">
                <span className="talent-status-dot talent-status-submitted" />
                Сдал ({submittedPlayers.length})
              </h3>
              {submittedPlayers.length > 0 ? (
                <table className="talent-table">
                  <thead>
                    <tr>
                      <th>Игрок</th>
                      <th>Сдано</th>
                    </tr>
                  </thead>
                  <tbody>
                    {submittedPlayers.map(p => (
                      <tr key={p.nick}>
                        <td className="talent-nick">{p.nick}</td>
                        <td className="talent-submitted">{p.totalContributed}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="talent-empty">Нет сдавших</div>
              )}
            </section>

            <section className="talent-section">
              <h3 className="talent-section-title">
                <span className="talent-status-dot talent-status-notsubmitted" />
                Не сдавал ({notSubmittedPlayers.length})
              </h3>
              {notSubmittedPlayers.length > 0 ? (
                <table className="talent-table">
                  <thead>
                    <tr>
                      <th>Игрок</th>
                    </tr>
                  </thead>
                  <tbody>
                    {notSubmittedPlayers.map(p => (
                      <tr key={p.nick}>
                        <td className="talent-nick">{p.nick}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="talent-empty">Нет должников</div>
              )}
            </section>
          </div>
        </>
      )}

      {!monthSummary && (
        <div className="talent-empty">Нет данных по ресурсам</div>
      )}
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
