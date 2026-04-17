import { useMemo } from 'react';
import type { TreasuryOperationData } from '../../types/clanInfo';
import { isTalentOperation, isTalentResource, getOriginalOwner, TALENT_RESOURCES, TALENT_RESOURCE_GROUPS } from '../../utils/treasury';
import './TalentAnalytics.css';

interface TalentAnalyticsProps {
  operations: TreasuryOperationData[];
}

interface PlayerResourceSummary {
  nick: string;
  totalContributed: number;
  resourceCount: number;
  resources: Record<string, number>;
}

interface ResourceSummary {
  resource: string;
  total: number;
  players: number;
}

interface GroupedResourceSummary {
  groupName: string;
  resources: ResourceSummary[];
  totalUnits: number;
}

export function TalentAnalytics({ operations }: TalentAnalyticsProps) {
  const talentOperations = useMemo(() => {
    return operations.filter(op => {
      if (isTalentOperation(op)) return true;
      if (op.operation_type === 'Возвращено главой' && isTalentResource(op.object_name)) {
        return true;
      }
      return false;
    });
  }, [operations]);

  const playerSummaries = useMemo((): PlayerResourceSummary[] => {
    const byPlayer: Record<string, { total: number; resources: Record<string, number> }> = {};

    for (const op of talentOperations) {
      let owner = op.nick;
      if (op.operation_type === 'Возвращено главой') {
        owner = getOriginalOwner(op, operations);
      }

      if (!byPlayer[owner]) {
        byPlayer[owner] = { total: 0, resources: {} };
      }
      byPlayer[owner].total += Math.abs(op.quantity);
      byPlayer[owner].resources[op.object_name] = (byPlayer[owner].resources[op.object_name] || 0) + Math.abs(op.quantity);
    }

    return Object.entries(byPlayer)
      .map(([nick, data]) => ({
        nick,
        totalContributed: data.total,
        resourceCount: Object.keys(data.resources).length,
        resources: data.resources,
      }))
      .sort((a, b) => b.totalContributed - a.totalContributed);
  }, [talentOperations, operations]);

  const resourceSummaries = useMemo((): ResourceSummary[] => {
    const byResource: Record<string, { total: number; players: Set<string> }> = {};

    for (const op of talentOperations) {
      if (!byResource[op.object_name]) {
        byResource[op.object_name] = { total: 0, players: new Set() };
      }
      byResource[op.object_name].total += Math.abs(op.quantity);
      
      let owner = op.nick;
      if (op.operation_type === 'Возвращено главой') {
        owner = getOriginalOwner(op, operations);
      }
      byResource[op.object_name].players.add(owner);
    }

    return Object.entries(byResource)
      .map(([resource, data]) => ({
        resource,
        total: data.total,
        players: data.players.size,
      }))
      .sort((a, b) => b.total - a.total);
  }, [talentOperations, operations]);

  const groupedResourceSummaries = useMemo((): GroupedResourceSummary[] => {
    return TALENT_RESOURCE_GROUPS.map(group => {
      const groupResources = group.resources
        .map(resName => resourceSummaries.find(r => r.resource === resName))
        .filter((r): r is ResourceSummary => r !== undefined);
      
      const totalUnits = groupResources.reduce((sum, r) => sum + r.total, 0);
      
      return {
        groupName: group.name,
        resources: groupResources,
        totalUnits,
      };
    }).filter(g => g.resources.length > 0);
  }, [resourceSummaries]);

  const topContributors = useMemo(() => playerSummaries.slice(0, 10), [playerSummaries]);

  const avgContribution = playerSummaries.length > 0
    ? playerSummaries.reduce((sum, p) => sum + p.totalContributed, 0) / playerSummaries.length
    : 0;

  const belowAveragePlayers = useMemo(() => {
    return playerSummaries.filter(p => p.totalContributed < avgContribution * 0.5);
  }, [playerSummaries, avgContribution]);

  const totalResourceUnits = talentOperations.reduce((sum, op) => sum + Math.abs(op.quantity), 0);

  return (
    <div className="talent-analytics">
      <header className="talent-header">
        <h2 className="talent-title">Ресурсы для прокачки талантов</h2>
      </header>

      <div className="talent-kpi">
        <div className="talent-kpi-card">
          <span className="talent-kpi-value">{totalResourceUnits.toLocaleString()}</span>
          <span className="talent-kpi-label">Всего единиц</span>
        </div>
        <div className="talent-kpi-card">
          <span className="talent-kpi-value">{TALENT_RESOURCES.length}</span>
          <span className="talent-kpi-label">Видов ресурсов</span>
        </div>
        <div className="talent-kpi-card">
          <span className="talent-kpi-value">{playerSummaries.length}</span>
          <span className="talent-kpi-label">Участников</span>
        </div>
        <div className="talent-kpi-card">
          <span className="talent-kpi-value">{avgContribution.toFixed(1)}</span>
          <span className="talent-kpi-label">Среднее на игрока</span>
        </div>
      </div>

      <div className="talent-grid">
        <section className="talent-section talent-section-wide">
          <h3 className="talent-section-title">Вклад по ресурсам</h3>
          {groupedResourceSummaries.length > 0 ? (
            <div className="talent-groups">
              {groupedResourceSummaries.map(group => (
                <div key={group.groupName} className="talent-group">
                  <div className="talent-group-header">
                    <span className="talent-group-name">{group.groupName}</span>
                    <span className="talent-group-total">{group.totalUnits} ед.</span>
                  </div>
                  <table className="talent-table">
                    <thead>
                      <tr>
                        <th>Ресурс</th>
                        <th>Всего</th>
                        <th>Игроков</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.resources.map(r => (
                        <tr key={r.resource}>
                          <td className="talent-resource">{r.resource}</td>
                          <td>{r.total}</td>
                          <td>{r.players}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          ) : (
            <div className="talent-empty">Нет данных</div>
          )}
        </section>

        <section className="talent-section">
          <h3 className="talent-section-title">Топ вкладчиков</h3>
          {topContributors.length > 0 ? (
            <table className="talent-table">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Всего</th>
                  <th>Видов</th>
                </tr>
              </thead>
              <tbody>
                {topContributors.map((p, idx) => (
                  <tr key={p.nick}>
                    <td className="talent-nick">
                      <span className="talent-rank">{idx + 1}</span>
                      {p.nick}
                    </td>
                    <td className="talent-amount">{p.totalContributed}</td>
                    <td>{p.resourceCount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="talent-empty">Нет данных</div>
          )}
        </section>

        <section className="talent-section talent-section-wide">
          <h3 className="talent-section-title">
            Детализация по игрокам
            <span className="talent-section-subtitle"> ({playerSummaries.length} участников)</span>
          </h3>
          {playerSummaries.length > 0 ? (
            <table className="talent-table talent-table-wide">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Всего</th>
                  {TALENT_RESOURCES.slice(0, 5).map(r => (
                    <th key={r}>{r.length > 15 ? r.slice(0, 15) + '...' : r}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {playerSummaries.slice(0, 20).map(p => (
                  <tr key={p.nick}>
                    <td className="talent-nick">{p.nick}</td>
                    <td className="talent-amount">{p.totalContributed}</td>
                    {TALENT_RESOURCES.slice(0, 5).map(r => (
                      <td key={r}>{p.resources[r] || '-'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="talent-empty">Нет данных</div>
          )}
        </section>

        {belowAveragePlayers.length > 0 && (
          <section className="talent-section">
            <h3 className="talent-section-title talent-section-warning">
              Ниже среднего ({belowAveragePlayers.length})
            </h3>
            <table className="talent-table">
              <thead>
                <tr>
                  <th>Игрок</th>
                  <th>Вклад</th>
                  <th>Дефицит</th>
                </tr>
              </thead>
              <tbody>
                {belowAveragePlayers.slice(0, 10).map(p => (
                  <tr key={p.nick}>
                    <td className="talent-nick">{p.nick}</td>
                    <td>{p.totalContributed}</td>
                    <td className="talent-deficit">-{Math.max(0, Math.round(avgContribution - p.totalContributed))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </div>
  );
}