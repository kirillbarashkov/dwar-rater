/** Займы из казны: минусовые операции, не закрытые подтверждённой парой. */

/** Сводка по одному человеку. */
export interface LoanPerson {
  nick: string;
  /** Сколько минусовых операций числится за человеком. */
  count: number;
  /** Сколько всего взято — положительное число. */
  taken: number;
  first_date: string;
  last_date: string;
  /** Разбивка по причинам: none | candidate | rejected | split. */
  reasons: Record<string, number>;
}

export interface LoanOperation {
  id: number;
  nick: string;
  date: string;
  operation_type: string;
  object_name: string;
  quantity: number;
  taken: number;
  reason: string;
  /** Пара, в которой операция состоит: по ней казначей переходит в разбор. */
  pair_id: number | null;
  pair_status: string | null;
}

export interface TreasuryLoansResponse {
  people: LoanPerson[];
  totals: {
    people: number;
    ops: number;
    taken: number;
    /** Сколько минусовых операций скрыто правилами групп исключений. */
    excluded_hidden: number;
  };
  /** Человеческие подписи причин: их считает бэкенд, чтобы слова не разъезжались. */
  reason_labels: Record<string, string>;
  /** Операции человека — только в ответе на запрос с ником. */
  ops?: LoanOperation[];
}
