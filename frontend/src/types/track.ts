export interface ImprovementStep {
  id: string;
  type: 'equipment' | 'medal' | 'stat' | 'effect';
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  impact: number;
  current: number | null;
  target: number | Record<string, unknown> | string | null;
  completed: boolean;
}

export interface ImprovementTrack {
  id: number;
  character_nick: string;
  scenario_id: number | null;
  steps: ImprovementStep[];
  total_progress: number;
  updated_at: string;
}

export interface TrackSummary {
  id: number;
  character_nick: string;
  scenario_id: number | null;
  total_progress: number;
  created_at: string;
  updated_at: string;
}
