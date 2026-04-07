export interface ScenarioSummary {
  id: number;
  name: string;
  description: string;
  is_public: boolean;
  created_by: number | null;
  created_at: string;
}

export interface ScenarioDetail extends ScenarioSummary {
  data: ScenarioData;
}

export interface ScenarioData {
  target_stats: Record<string, string | number>;
  recommended_equipment: RecommendedEquipment[];
  priority_medals: string[];
  milestones: Milestone[];
}

export interface RecommendedEquipment {
  slot: string;
  min_quality: string;
  stats: string[];
}

export interface Milestone {
  level: number;
  target_stats: Record<string, string | number>;
}

export interface GapAnalysis {
  stat: string;
  current: number;
  target: number;
  diff: number;
  progress_pct: number;
}

export interface ScenarioComparisonResult {
  scenario_name: string;
  gaps: GapAnalysis[];
  recommended_equipment: RecommendedEquipment[];
  priority_medals: string[];
  milestones: Milestone[];
}
