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
