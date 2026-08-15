export type TargetType = 'character' | 'snapshot' | 'scenario';
export type StepPhase = 'level' | 'reputation' | 'equipment' | 'stats' | 'medals';
export type Effort = 'low' | 'medium' | 'high';

export interface ImprovementStep {
  id: string;
  type: 'equipment' | 'medal' | 'stat' | 'effect' | 'hp' | 'level';
  phase: StepPhase;
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  impact: number;
  effort: Effort;
  roi: number;
  gate?: { type: 'level' | 'reputation'; value: string };
  current: number | string | null;
  target: number | string | Record<string, unknown> | null;
  delta: number;
  pct: number;
  completed: boolean;
  completed_auto?: boolean;
}

export interface TrackPhase {
  id: StepPhase;
  title: string;
  step_ids: string[];
  progress_pct: number;
}

export interface CharacterSummary {
  name: string;
  level: string;
  main_stats: Record<string, string>;
  hp?: string;
  power?: number;
}

export interface ImprovementTrack {
  id: number;
  character_nick: string;
  scenario_id: number | null;
  target_type: TargetType;
  target_ref: string | null;
  steps: ImprovementStep[];
  phases: TrackPhase[];
  total_progress: number;
  power_gap: number;
  source_summary: CharacterSummary;
  target_summary: CharacterSummary;
  updated_at: string;
  created_at?: string;
}

export interface TrackSummary {
  id: number;
  character_nick: string;
  scenario_id: number | null;
  target_type?: TargetType;
  target_ref?: string | null;
  total_progress: number;
  power_gap?: number;
  created_at: string;
  updated_at: string;
}

export interface ReEvaluateResult {
  id: number;
  steps: ImprovementStep[];
  phases: TrackPhase[];
  power_gap: number;
  total_progress: number;
}

export interface GenerateTrackPayload {
  source: AnalysisLike;
  target_type: TargetType;
  target_ref: string;
  force_refresh?: boolean;
}

/** Structural subset of AnalysisResult sufficient for the backend. */
export type AnalysisLike = Record<string, unknown>;
