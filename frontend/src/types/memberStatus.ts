import type { TreasuryPairData } from './treasuryPairs';

/** Налог участника за месяц — из того же реестра, что и вкладка «Сальдо». */
export interface MemberTaxStatus {
  norm: number;
  paid: number;
  compensation: number;
  carried_in: number;
  debt: number;
  balance: number;
  /** Сальдо со знаком плюс — переплата, которая переносится дальше. */
  credit: number;
  level: number | null;
}

export interface MemberResourceTotal {
  operation_type: string;
  object_name: string;
  total: number;
}

export interface MemberHistoryItem {
  id: number;
  date: string;
  operation_type: string;
  object_name: string;
  quantity: number;
  op_class: string;
}

export interface MemberStatusResponse {
  nick: string;
  month: number;
  year: number;
  tax: MemberTaxStatus;
  resources: MemberResourceTotal[];
  pairs: {
    confirmed: TreasuryPairData[];
    candidates: TreasuryPairData[];
    rejected: TreasuryPairData[];
  };
  history: MemberHistoryItem[];
}
