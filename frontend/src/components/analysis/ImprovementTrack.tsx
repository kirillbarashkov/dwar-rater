import { useState, useEffect } from 'react';
import type { ImprovementStep } from '../../types/track';
import { generateTrack, updateStep } from '../../api/tracks';
import type { AnalysisResult } from '../../types/character';
import type { ScenarioSummary } from '../../types/scenario';
import { getScenarios } from '../../api/scenarios';
import './ImprovementTrack.css';

interface ImprovementTrackPanelProps {
  character: AnalysisResult;
}

function StepItem({ step, onToggle }: { step: ImprovementStep; onToggle: (id: string) => void }) {
  const priorityColors: Record<string, string> = {
    high: '#dc3545',
    medium: 'var(--gold)',
    low: 'var(--text-muted)',
  };

  const typeLabels: Record<string, string> = {
    stat: 'Стат',
    equipment: 'Экипировка',
    medal: 'Медаль',
    effect: 'Эффект',
  };

  return (
    <div className={`track-step ${step.completed ? 'step-completed' : ''}`}>
      <input
        type="checkbox"
        checked={step.completed}
        onChange={() => onToggle(step.id)}
        className="step-checkbox"
      />
      <div className="step-content">
        <div className="step-header">
          <span className={`step-priority`} style={{ backgroundColor: priorityColors[step.priority] }}>
            {step.priority}
          </span>
          <span className="step-type">{typeLabels[step.type] || step.type}</span>
          <span className={`step-title ${step.completed ? 'step-title-done' : ''}`}>
            {step.title}
          </span>
        </div>
        <p className="step-desc">{step.description}</p>
      </div>
    </div>
  );
}

export function ImprovementTrackPanel({ character }: ImprovementTrackPanelProps) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<number | null>(null);
  const [steps, setSteps] = useState<ImprovementStep[]>([]);
  const [trackId, setTrackId] = useState<number | null>(null);
  const [totalProgress, setTotalProgress] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasTrack, setHasTrack] = useState(false);

  const handleGenerate = async () => {
    if (!selectedScenario) return;
    setIsLoading(true);
    try {
      const result = await generateTrack(character as unknown as Record<string, unknown>, selectedScenario);
      setSteps(result.steps);
      setTrackId(result.id);
      setTotalProgress(result.total_progress);
      setHasTrack(true);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggle = async (stepId: string) => {
    if (!trackId) return;
    const step = steps.find((s) => s.id === stepId);
    if (!step) return;
    try {
      const result = await updateStep(trackId, stepId, !step.completed);
      setSteps(result.steps);
      setTotalProgress(result.total_progress);
    } catch {
      // ignore
    }
  };

  const handleLoadScenarios = async () => {
    try {
      const data = await getScenarios();
      setScenarios(data);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    handleLoadScenarios();
  }, []);

  if (!hasTrack) {
    return (
      <div className="improvement-track">
        <h3 className="it-title">Треп улучшений</h3>
        {scenarios.length === 0 ? (
          <p className="it-placeholder">Сценарии прокачки пока не созданы</p>
        ) : (
          <div className="it-generate">
            <select
              className="it-select"
              value={selectedScenario || ''}
              onChange={(e) => setSelectedScenario(Number(e.target.value))}
            >
              <option value="" disabled>Выберите сценарий</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleGenerate}
              disabled={!selectedScenario || isLoading}
            >
              {isLoading ? 'Генерация...' : 'Создать трек'}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="improvement-track">
      <div className="it-header">
        <h3 className="it-title">Треп улучшений</h3>
        <div className="it-progress">
          <div className="it-progress-bar">
            <div className="it-progress-fill" style={{ width: `${totalProgress}%` }} />
          </div>
          <span className="it-progress-pct">{totalProgress}%</span>
        </div>
      </div>
      <div className="it-steps">
        {steps.map((step) => (
          <StepItem key={step.id} step={step} onToggle={handleToggle} />
        ))}
      </div>
    </div>
  );
}
