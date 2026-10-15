/** Правило группы исключений: сопоставление по началу названия ресурса. */
export interface ExclusionRule {
  id: number;
  prefix: string;
}

/** Группа исключений казны. */
export interface ExclusionGroup {
  id: number;
  name: string;
  /** 'exclude' — не попадать ни в один отчёт казны, 'neutral' — не сдача, но видно в журнале. */
  mode: 'exclude' | 'neutral' | string;
  comment: string;
  is_active: boolean;
  created_at: string | null;
  rules: ExclusionRule[];
}

export interface ExclusionGroupsResponse {
  items: ExclusionGroup[];
}
