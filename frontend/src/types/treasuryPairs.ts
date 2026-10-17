/** Сторона пары: операция казны, участвующая в обмене или долге. */
export interface TreasuryPairSide {
  id: number;
  date: string;
  nick: string;
  operation_type: string;
  object_name: string;
  quantity: number;
  op_class: string;
  /** Пусто, 'exchange', 'loan' или 'talents' — к чему отнесена операция. */
  class_kind: string;
}

/** Пара казны: предложение автоматики или уже принятое решение казначея. */
export interface TreasuryPairData {
  id: number;
  kind: 'exchange' | 'loan' | string;
  status: 'candidate' | 'confirmed' | 'rejected' | string;
  comment: string | null;
  created_at: string | null;
  confirmed_at: string | null;
  first: TreasuryPairSide | null;
  second: TreasuryPairSide | null;
}

export interface TreasuryPairsResponse {
  total: number;
  items: TreasuryPairData[];
  /** Сколько пар-кандидатов скрыто: их объекты выведены из отчётов группами исключений. */
  hidden_excluded?: number;
}

/** Итог пересборки предложений по парам. */
export interface TreasuryRecalcResult {
  /** Сколько предложений и отклонённых пар убрано перед пересборкой. */
  removed: number;
  /** Сколько из убранных были отклонены — они вернутся на повторный разбор. */
  rejected_freed: number;
  /** Операции, участвовавшие в поиске. */
  freed_ops: number;
  /** Операции в подтверждённых парах и разрывах — решения казначея, поиск их не трогает. */
  locked_ops: number;
  /** Сколько предложений создано заново. */
  created: number;
  /** Распределение классов операций до и после: должно совпадать. */
  classes_before: Record<string, number>;
  classes_after: Record<string, number>;
}

/** Запись истории решений по паре: правка сервиса или действие казначея. */
export interface TreasuryPairHistoryEntry {
  source: 'revision' | 'audit' | string;
  action: string;
  changed_by: number | null;
  changed_by_name: string;
  old: string | null;
  new: string | null;
  comment: string;
  at: string | null;
}

export interface TreasuryPairHistoryResponse {
  pair_id: number;
  entries: TreasuryPairHistoryEntry[];
}

/** Кандидат на вторую сторону операции, с оценкой похожести. */
export interface TreasuryPairCandidate {
  score: number;
  id: number;
  date: string;
  nick: string;
  operation_type: string;
  object_name: string;
  quantity: number;
}

export interface TreasuryCandidatesResponse {
  first: TreasuryPairCandidate;
  candidates: TreasuryPairCandidate[];
}
