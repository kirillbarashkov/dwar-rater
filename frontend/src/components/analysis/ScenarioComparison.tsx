import { useState, useEffect } from 'react';
import type { ScenarioComparisonResult, GapAnalysis, ScenarioSummary } from '../../types/scenario';
import { getScenarios, compareScenario } from '../../api/scenarios';
import type { AnalysisResult } from '../../types/character';
import './ScenarioComparison.css';

interface ScenarioComparisonProps {
  character: AnalysisResult;
}

function ProgressBar({ gap }: { gap: GapAnalysis }) {
  const isComplete = gap.progress_pct >= 100;
  const isClose = gap.progress_pct >= 70 && !isComplete;

  return (
    <div className="gap-item">
      <div className="gap-header">
        <span className="gap-stat">{gap.stat}</span>
        <span className="gap-values">
          {gap.current} / {gap.target}
          {gap.diff > 0 && (
            <span className="gap-diff">+{gap.diff}</span>
          )}
        </span>
      </div>
      <div className="progress-bar">
        <div
          className={`progress-fill ${isComplete ? 'complete' : isClose ? 'close' : 'far'}`}
          style={{ width: `${Math.min(gap.progress_pct, 100)}%` }}
        />
      </div>
      <span className="progress-pct">{gap.progress_pct}%</span>
    </div>
  );
}

export function ScenarioComparison({ character }: ScenarioComparisonProps) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<ScenarioComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    getScenarios().then(setScenarios).catch(() => setScenarios([]));
  }, []);

  const handleCompare = async () => {
    if (!selectedId) return;
    setIsLoading(true);
    try {
      const result = await compareScenario(selectedId, character as unknown as Record<string, unknown>);
      setComparison(result);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  if (scenarios.length === 0) {
    return null;
  }

  return (
    <div className="scenario-comparison">
      <div className="sc-selector">
        <select
          className="sc-select"
          value={selectedId || ''}
          onChange={(e) => { setSelectedId(Number(e.target.value)); setComparison(null); }}
        >
          <option value="" disabled>Выберите сценарий</option>
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <button
          className="btn btn-primary btn-sm"
          onClick={handleCompare}
          disabled={!selectedId || isLoading}
        >
          {isLoading ? 'Сравнение...' : 'Сравнить'}
        </button>
      </div>

      {comparison && (
        <div className="sc-result">
          <h3 className="sc-result-title">{comparison.scenario_name}</h3>

          <div className="sc-gaps">
            <h4>Разрывы по характеристикам</h4>
            {comparison.gaps.map((g) => (
              <ProgressBar key={g.stat} gap={g} />
            ))}
          </div>

          {comparison.recommended_equipment.length > 0 && (
            <div className="sc-recommended">
              <h4>Рекомендуемая экипировка</h4>
              {comparison.recommended_equipment.map((eq, i) => (
                <div key={i} className="rec-item">
                  <span className="rec-slot">{eq.slot}</span>
                  <span className="rec-quality">Мин. качество: {eq.min_quality}</span>
                  <span className="rec-stats">{eq.stats.join(', ')}</span>
                </div>
              ))}
            </div>
          )}

          {comparison.priority_medals.length > 0 && (
            <div className="sc-medals">
              <h4>Приоритетные медали</h4>
              <div className="medal-tags">
                {comparison.priority_medals.map((m, i) => (
                  <span key={i} className="medal-tag">{m}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
