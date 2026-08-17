import { useState, useEffect, useMemo } from 'react';
import type { ImprovementStep, TrackPhase, TargetType, CharacterSummary } from '../../types/track';
import { generateTrack, updateStep, reEvaluateTrack } from '../../api/tracks';
import { getCompareCharacters } from '../../api/compare';
import type { AnalysisResult } from '../../types/character';
import type { ScenarioSummary } from '../../types/scenario';
import { getScenarios } from '../../api/scenarios';
import './ImprovementTrack.css';

interface ImprovementTrackPanelProps {
  character?: AnalysisResult | null;
}

const effortLabels: Record<string, string> = {
  low: 'низкие',
  medium: 'средние',
  high: 'высокие',
};

const phaseIcons: Record<string, string> = {
  level: '🛡',
  reputation: '🏅',
  equipment: '⚔️',
  stats: '📈',
  medals: '🎖',
};

function StepItem({ step, onToggle }: { step: ImprovementStep; onToggle: (id: string) => void }) {
  const priorityColors: Record<string, string> = {
    high: '#dc3545',
    medium: 'var(--gold)',
    low: 'var(--text-muted)',
  };

  const typeLabels: Record<string, string> = {
    stat: 'Стат',
    hp: 'HP',
    equipment: 'Экипировка',
    medal: 'Медаль',
    effect: 'Эффект',
    level: 'Уровень',
  };

  const hasBreakdown = step.type === 'stat' || step.type === 'hp' || step.type === 'level';

  return (
    <div className={`track-step ${step.completed ? 'step-completed' : ''}`}>
      <input
        type="checkbox"
        checked={step.completed}
        onChange={() => onToggle(step.id)}
        className="step-checkbox"
        title={step.completed_auto ? 'Авто-отмечено по анализу' : undefined}
      />
      <div className="step-content">
        <div className="step-header">
          <span className="step-priority" style={{ backgroundColor: priorityColors[step.priority] }}>
            {step.priority}
          </span>
          <span className="step-type">{typeLabels[step.type] || step.type}</span>
          <span className={`step-title ${step.completed ? 'step-title-done' : ''}`}>{step.title}</span>
          <span className={`step-badge effort-${step.effort}`}>⚡ {effortLabels[step.effort] || step.effort}</span>
          <span className="step-badge roi">ROI {step.roi}</span>
        </div>
        <p className="step-desc">{step.description}</p>
        {hasBreakdown && (
          <div className="step-breakdown">
            <code>
              {step.current ?? '—'} → {typeof step.target === 'number' ? step.target : '—'} (Δ=+
              {step.delta}, {step.pct}%)
            </code>
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ title, summary }: { title: string; summary: CharacterSummary }) {
  return (
    <div className="it-summary-card">
      <span className="it-summary-title">{title}</span>
      <span className="it-summary-name">{summary?.name || '—'}</span>
      <span className="it-summary-level">Уровень: {summary?.level || '—'}</span>
      <span className="it-summary-hp">HP: {summary?.hp || '—'}</span>
      {summary?.main_stats &&
        Object.entries(summary.main_stats)
          .slice(0, 3)
          .map(([stat, value]) => (
            <span key={stat} className="it-summary-stat">
              {stat}: {value}
            </span>
          ))}
    </div>
  );
}

function DiffView({ steps, source, target }: {
  steps: ImprovementStep[];
  source: CharacterSummary;
  target: CharacterSummary;
}) {
  const rows = useMemo(() => {
    return steps
      .filter((s) => s.type === 'stat' || s.type === 'hp' || s.type === 'level')
      .slice(0, 12)
      .map((s) => ({
        id: s.id,
        title: s.title,
        current: s.current,
        target: typeof s.target === 'number' ? s.target : '—',
        delta: s.delta,
        pct: s.pct,
      }));
  }, [steps]);

  return (
    <div className="it-diff">
      <div className="it-diff-header">
        <span className="it-diff-col">{source?.name || 'source'}</span>
        <span className="it-diff-col">{target?.name || 'target'}</span>
      </div>
      <table className="it-diff-table">
        <thead>
          <tr>
            <th>Параметр</th>
            <th>Source</th>
            <th>Target</th>
            <th>Δ</th>
            <th>%</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.title}</td>
              <td>{r.current ?? '—'}</td>
              <td>{r.target}</td>
              <td>+{r.delta}</td>
              <td>{r.pct}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      {steps.some((s) => s.type === 'medal') && (
        <div className="it-diff-medals">
          <span className="it-diff-title">Недостающие медали:</span>
          {steps
            .filter((s) => s.type === 'medal')
            .map((s) => (
              <span key={s.id} className="it-diff-medal">
                🎖 {typeof s.target === 'string' ? s.target : s.title}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

export function ImprovementTrackPanel({ character }: ImprovementTrackPanelProps) {
  const [targetType, setTargetType] = useState<TargetType>('scenario');
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [snapshots, setSnapshots] = useState<{ id: number; name: string; added_at: string }[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<number | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<number | null>(null);
  const [targetUrl, setTargetUrl] = useState('');
  const [forceRefresh, setForceRefresh] = useState(false);

  const [track, setTrack] = useState<{
    id: number;
    steps: ImprovementStep[];
    phases: TrackPhase[];
    total_progress: number;
    power_gap: number;
    source_summary: CharacterSummary;
    target_summary: CharacterSummary;
  } | null>(null);
  const [collapsedPhases, setCollapsedPhases] = useState<Record<string, boolean>>({});
  const [showDiff, setShowDiff] = useState(false);
  const [resyncNotice, setResyncNotice] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadTargets = async () => {
    try {
      const [sc, sn] = await Promise.all([getScenarios(), getCompareCharacters()]);
      setScenarios(sc);
      setSnapshots(sn.map((s) => ({ id: s.id, name: s.name, added_at: s.added_at })));
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadTargets();
  }, []);

  const handleGenerate = async () => {
    const targetRef =
      targetType === 'scenario'
        ? selectedScenario !== null
          ? String(selectedScenario)
          : ''
        : targetType === 'snapshot'
          ? selectedSnapshot !== null
            ? String(selectedSnapshot)
            : ''
          : targetUrl.trim();
    if (!targetRef) return;

    setIsLoading(true);
    setResyncNotice(null);
    try {
      const result = await generateTrack({
        source: character as unknown as Record<string, unknown>,
        target_type: targetType,
        target_ref: targetRef,
        force_refresh: forceRefresh,
      });
      setTrack(result);
      setCollapsedPhases({});
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggle = async (stepId: string) => {
    if (!track) return;
    const step = track.steps.find((s) => s.id === stepId);
    if (!step) return;
    try {
      const result = await updateStep(track.id, stepId, !step.completed);
      setTrack({ ...track, steps: result.steps, total_progress: result.total_progress });
    } catch {
      // ignore
    }
  };

  const handleReEvaluate = async () => {
    if (!track) return;
    setIsLoading(true);
    setResyncNotice(null);
    try {
      const before = track.steps.filter((s) => s.completed).map((s) => s.id);
      const result = await reEvaluateTrack(
        track.id,
        character as unknown as Record<string, unknown>,
      );
      const after = result.steps.filter((s) => s.completed).map((s) => s.id);
      const autoDone = after.filter((id) => !before.includes(id)).length;
      const autoUndone = before.filter((id) => !after.includes(id)).length;
      const parts: string[] = [];
      if (autoDone) parts.push(`Авто-отмечено: ${autoDone}`);
      if (autoUndone) parts.push(`Снято: ${autoUndone}`);
      setResyncNotice(parts.length ? parts.join(' · ') : 'Изменений нет — цель достигнута по всем фактам');
      setTrack({
        ...track,
        steps: result.steps,
        phases: result.phases,
        total_progress: result.total_progress,
        power_gap: result.power_gap,
      });
    } catch {
      setResyncNotice('Не удалось пересчитать');
    } finally {
      setIsLoading(false);
    }
  };

  const togglePhase = (phaseId: string) => {
    setCollapsedPhases((prev) => ({ ...prev, [phaseId]: !prev[phaseId] }));
  };

  const targetRefEmpty =
    targetType === 'character'
      ? !targetUrl.trim()
      : targetType === 'snapshot'
        ? selectedSnapshot === null
        : selectedScenario === null;

  if (!character) {
    return (
      <div className="improvement-track">
        <h3 className="it-title">Трек улучшений</h3>
        <div className="it-empty-help">
          <p className="it-help-heading">Трек — это пошаговый план прокачки вашего персонажа до цели.</p>
          <p className="it-help-note">
            <strong>Персонаж ещё не выбран.</strong> Введите ник в поле «Анализ персонажа» выше и нажмите
            «Анализировать» — трек строится от текущих характеристик вашего персонажа. Пока анализа нет,
            создать трек нельзя.
          </p>
          <ol className="it-help-steps">
            <li>Введите ник персонажа в поле «Анализ персонажа» наверху страницы и нажмите «Анализировать».</li>
            <li>Вернитесь на эту вкладку и выберите цель: персонаж по ссылке, сохранённый снапшот или сценарий.</li>
            <li>Нажмите «Создать трек» — мы сравним вашего персонажа с целью и построим шаги по приоритету.</li>
          </ol>
        </div>
      </div>
    );
  }

  if (!track) {
    return (
      <div className="improvement-track">
        <h3 className="it-title">Трек улучшений</h3>
        <div className="it-empty-help">
          <p className="it-help-heading">Трек — это пошаговый план прокачки вашего персонажа до цели.</p>
          <ol className="it-help-steps">
            <li>Выберите цель: персонаж по ссылке с dwar.ru, сохранённый снапшот или готовый сценарий прокачки.</li>
            <li>Нажмите «Создать трек» — мы сравним вашего персонажа с целью и построим шаги по приоритету.</li>
            <li>Отмечайте выполненные шаги или жмите «Пересчитать» после повторного анализа — прогресс обновится автоматически.</li>
          </ol>
          <p className="it-help-note">
            <strong>Нет персонажа для сравнения?</strong> Сначала введите ник в поле «Анализ персонажа» наверху
            страницы и дождитесь результатов — трек строится от текущих характеристик вашего персонажа.
          </p>
        </div>
        <div className="it-target-selector">
          <div className="it-target-modes">
            <label className={`it-mode ${targetType === 'character' ? 'active' : ''}`}>
              <input
                type="radio"
                name="target-type"
                checked={targetType === 'character'}
                onChange={() => setTargetType('character')}
              />
              Персонаж по URL
            </label>
            <label className={`it-mode ${targetType === 'snapshot' ? 'active' : ''}`}>
              <input
                type="radio"
                name="target-type"
                checked={targetType === 'snapshot'}
                onChange={() => setTargetType('snapshot')}
              />
              Снапшот
            </label>
            <label className={`it-mode ${targetType === 'scenario' ? 'active' : ''}`}>
              <input
                type="radio"
                name="target-type"
                checked={targetType === 'scenario'}
                onChange={() => setTargetType('scenario')}
              />
              Сценарий
            </label>
          </div>

          {targetType === 'character' && (
            <input
              type="text"
              className="it-input"
              placeholder="https://w1.dwar.ru/user_info.php?nick=..."
              value={targetUrl}
              onChange={(e) => setTargetUrl(e.target.value)}
            />
          )}
          {targetType === 'snapshot' && (
            snapshots.length === 0 ? (
              <p className="it-placeholder">Нет сохранённых снапшотов для сравнения</p>
            ) : (
              <select
                className="it-select"
                value={selectedSnapshot ?? ''}
                onChange={(e) => setSelectedSnapshot(Number(e.target.value))}
              >
                <option value="" disabled>Выберите снапшот</option>
                {snapshots.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({new Date(s.added_at).toLocaleDateString()})
                  </option>
                ))}
              </select>
            )
          )}
          {targetType === 'scenario' && (
            scenarios.length === 0 ? (
              <p className="it-placeholder">Сценарии прокачки пока не созданы</p>
            ) : (
              <select
                className="it-select"
                value={selectedScenario ?? ''}
                onChange={(e) => setSelectedScenario(Number(e.target.value))}
              >
                <option value="" disabled>Выберите сценарий</option>
                {scenarios.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            )
          )}

          <label className="it-force-refresh">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(e) => setForceRefresh(e.target.checked)}
            />
            Перепроверить моего персонажа (по URL из профиля)
          </label>

          <button
            className="btn btn-primary btn-sm"
            onClick={handleGenerate}
            disabled={isLoading || targetRefEmpty}
          >
            {isLoading ? 'Генерация...' : 'Создать трек'}
          </button>
        </div>
      </div>
    );
  }

  const phasesList = track.phases || [];
  const stepsById = new Map(track.steps.map((s) => [s.id, s]));

  return (
    <div className="improvement-track">
      <div className="it-header">
        <h3 className="it-title">
          Трек улучшений: {track.source_summary?.name || character.name} →{' '}
          {track.target_summary?.name || 'цель'}
        </h3>
        <span className="it-power-gap" title="Суммарный взвешенный разрыв мощности">
          gap: {track.power_gap}
        </span>
        <button
          className="btn btn-ghost btn-sm it-reevaluate"
          onClick={handleReEvaluate}
          disabled={isLoading}
          title="Сравнит вашего персонажа с зафиксированным таргетом и обновит статус шагов"
        >
          ⟳ Пересчитать
        </button>
        <div className="it-progress">
          <div className="it-progress-bar">
            <div className="it-progress-fill" style={{ width: `${track.total_progress}%` }} />
          </div>
          <span className="it-progress-pct">{track.total_progress}%</span>
        </div>
      </div>

      <div className="it-summaries">
        <SummaryCard title="Source" summary={track.source_summary} />
        <SummaryCard title="Target" summary={track.target_summary} />
      </div>

      {resyncNotice && <div className="it-resync-notice">{resyncNotice}</div>}

      {phasesList.map((phase) => {
        const collapsed = collapsedPhases[phase.id];
        const phaseSteps = phase.step_ids
          .map((id) => stepsById.get(id))
          .filter((s): s is ImprovementStep => Boolean(s));
        return (
          <div key={phase.id} className="it-phase">
            <button className="it-phase-header" onClick={() => togglePhase(phase.id)}>
              <span className="it-phase-icon">{phaseIcons[phase.id] || '▸'}</span>
              <span className="it-phase-title">{phase.title}</span>
              <span className="it-phase-count">
                {phaseSteps.filter((s) => s.completed).length}/{phaseSteps.length}
              </span>
              <div className="it-phase-progress">
                <div className="it-phase-progress-bar">
                  <div className="it-phase-progress-fill" style={{ width: `${phase.progress_pct}%` }} />
                </div>
                <span className="it-phase-pct">{phase.progress_pct}%</span>
              </div>
              <span className="it-phase-chevron">{collapsed ? '▸' : '▾'}</span>
            </button>
            {!collapsed && (
              <div className="it-phase-steps">
                {phaseSteps.map((step) => (
                  <StepItem key={step.id} step={step} onToggle={handleToggle} />
                ))}
              </div>
            )}
          </div>
        );
      })}

      <button className="btn btn-ghost btn-sm it-diff-toggle" onClick={() => setShowDiff((v) => !v)}>
        {showDiff ? 'Скрыть сравнение' : 'Сравнить source ↔ target'}
      </button>
      {showDiff && (
        <DiffView steps={track.steps} source={track.source_summary} target={track.target_summary} />
      )}
    </div>
  );
}
