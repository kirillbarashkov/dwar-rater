

export interface ParsedTreasuryOperation {
  date: string;
  nick: string;
  operation_type: string;
  object_name: string;
  quantity: number;
}

export function parseTreasuryOperations(html: string): ParsedTreasuryOperation[] {
  const operations: ParsedTreasuryOperation[] = [];

  const rowRegex = /<tr\s*class="[^"]*">(.*?)<\/tr>/gs;
  const dateRegex = /(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})/;
  const nickRegex = /userToTag\(\s*'([^']+)'\s*\)/;

  const cleanHtml = (htmlContent: string): string => {
    return htmlContent
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&')
      .trim();
  };

  let rowMatch;
  while ((rowMatch = rowRegex.exec(html)) !== null) {
    const rowHtml = rowMatch[1];
    const cells: string[] = [];
    const cellStyles: string[] = [];

    const tdRegex = /<td[^>]*class="brd-all p6h"([^>]*)>(.*?)<\/td>/gs;
    let tdMatch;
    while ((tdMatch = tdRegex.exec(rowHtml)) !== null) {
      cellStyles.push(tdMatch[1]);
      cells.push(tdMatch[2]);
    }

    if (cells.length < 5) continue;

    const dateMatch = dateRegex.exec(cells[0]);
    if (!dateMatch) continue;
    const date = dateMatch[1];

    const nickMatch = nickRegex.exec(cells[1]);
    if (!nickMatch) continue;
    const nick = nickMatch[1];

    const operation_type = cleanHtml(cells[2]);
    const objectName = cleanHtml(cells[3]);

    const cell5Content = cells[4];
    const cell5Style = cellStyles[4] || '';
    const cleanCell5 = cleanHtml(cell5Content);

    const isGreen = /color:\s*green/i.test(cell5Style);
    const isRed = /color:\s*red/i.test(cell5Style);

    let quantity = 0;
    const direction = isGreen ? 1 : isRed ? -1 : 1;

    if (isGreen || isRed) {
      const numMatch = cleanCell5.match(/(-?\d+)/);
      if (numMatch) {
        quantity = Math.abs(parseInt(numMatch[1], 10));
      }
    }

    operations.push({
      date,
      nick,
      operation_type,
      object_name: objectName,
      quantity: quantity * direction,
    });
  }

  return operations;
}

export const TREASURY_WEB_URL = 'https://w1.dwar.ru/user_info.php';

export const TREASURY_CLAN_REPORT_URL =
  'https://w1.dwar.ru/clan_management.php?f=1&mode=clancell&submode=report';

export const MONTHS_RU = [
  '',
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
] as const;

export const PERIOD_OPTIONS = [
  { value: 'all', label: 'Все' },
  { value: 'today', label: 'Сегодня' },
  { value: 'month', label: 'Текущий месяц' },
  { value: 'range', label: 'Диапазон' },
] as const;

export type PeriodType = (typeof PERIOD_OPTIONS)[number]['value'];

export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const;

export type SortKey = 'date' | 'nick' | 'operation_type' | 'object_name' | 'quantity';

export const SORT_KEYS: SortKey[] = [
  'date',
  'nick',
  'operation_type',
  'object_name',
  'quantity',
];

export const SORT_KEY_LABELS: Record<SortKey, string> = {
  date: 'Дата',
  nick: 'Игрок',
  operation_type: 'Тип',
  object_name: 'Объект',
  quantity: 'Кол-во',
};

export interface ParsedDate {
  day: number;
  month: number;
  year: number;
}

export function parseDate(dateStr: string): ParsedDate | null {
  const match = dateStr.match(/(\d{2})\.(\d{2})\.(\d{4})/);
  if (!match) return null;
  return {
    day: parseInt(match[1], 10),
    month: parseInt(match[2], 10),
    year: parseInt(match[3], 10),
  };
}

export function formatDateKey(day: number, month: number, year: number): string {
  return `${day.toString().padStart(2, '0')}.${month.toString().padStart(2, '0')}.${year}`;
}

export interface MonthDay {
  day: number;
  dateKey: string;
  hasData: boolean;
}

export function getMonthDays(year: number, month: number): MonthDay[] {
  const daysInMonth = new Date(year, month, 0).getDate();
  const result: MonthDay[] = [];
  for (let d = 1; d <= daysInMonth; d++) {
    result.push({
      day: d,
      dateKey: formatDateKey(d, month, year),
      hasData: false,
    });
  }
  return result;
}

export const TALENT_RESOURCES = [
  'Кристаллы истины',
  'Страница из трактата «Единство клана»',
  'Трактат «Единство клана I»',
  'Трактат «Единство клана II»',
  'Трактат «Единство клана III»',
  'Трактат «Единство клана IV»',
  'Трактат «Единство клана V»',
  'Жетон «Времена года»',
  'Кристаллизованный прах',
  'Браслеты джиннов',
  'Мо-датхар альвы благонравной',
  'Мо-датхар нурида',
  'Мо-датхар золотой шамсы',
  'Боевое свидетельство',
  'Гиамбир',
  'Эльдорилл',
  'Золотой хабус',
  'Фосфорическая пыль',
  'Звено цепи Лудьиал',
  'Злое око',
  'Эфирная пыль',
] as const;

export type TalentResourceName = typeof TALENT_RESOURCES[number];

export interface TalentResourceGroup {
  name: string;
  resources: readonly string[];
}

export const TALENT_RESOURCE_GROUPS: TalentResourceGroup[] = [
  {
    name: 'Универсальные ресурсы',
    resources: ['Кристаллы истины'],
  },
  {
    name: 'Трактат «Единство клана»',
    resources: [
      'Страница из трактата «Единство клана»',
      'Трактат «Единство клана I»',
      'Трактат «Единство клана II»',
      'Трактат «Единство клана III»',
      'Трактат «Единство клана IV»',
      'Трактат «Единство клана V»',
    ],
  },
  {
    name: 'Жетон «Времена года»',
    resources: ['Жетон «Времена года»'],
  },
  {
    name: 'Кристаллизованный прах',
    resources: ['Кристаллизованный прах'],
  },
  {
    name: 'Мистрас: Ресурсы джиннов',
    resources: [
      'Браслеты джиннов',
      'Мо-датхар альвы благонравной',
      'Мо-датхар нурида',
      'Мо-датхар золотой шамсы',
    ],
  },
  {
    name: 'Клановые',
    resources: [
      'Боевое свидетельство',
      'Гиамбир',
      'Эльдорилл',
      'Золотой хабус',
    ],
  },
  {
    name: 'МКК',
    resources: [
      'Фосфорическая пыль',
      'Звено цепи Лудьиал',
      'Злое око',
      'Эфирная пыль',
    ],
  },
];

export const TAX_OBJECT_NAME = 'Монеты';

export const CLAN_TAX_NORM: Record<number, number> = {
  1: 10, 2: 10, 3: 10, 4: 10, 5: 10,
  6: 15, 7: 15, 8: 15,
  9: 20, 10: 20,
  11: 25, 12: 25,
  13: 50, 14: 50, 15: 50,
  16: 100, 17: 100, 18: 100, 19: 100, 20: 100,
};

export interface PlayerContribution {
  nick: string;
  total: number;
  count: number;
  details: Record<string, number>;
}

export interface TaxRecord {
  nick: string;
  amount: number;
  date: string;
  status: 'debtor' | 'normal' | 'over';
}

export function isTaxOperation(op: { operation_type: string; object_name: string }): boolean {
  return op.operation_type === 'Деньги' && op.object_name === TAX_OBJECT_NAME;
}

export function isTalentResource(objectName: string): boolean {
  return TALENT_RESOURCES.includes(objectName as TalentResourceName);
}

export function isTalentOperation(op: { operation_type: string; object_name: string }): boolean {
  if (op.operation_type === 'Склад' && isTalentResource(op.object_name)) {
    return true;
  }
  if (op.operation_type === 'Возвращено главой') {
    return isTalentResource(op.object_name);
  }
  return false;
}

export function isTaxRelevantOperation(op: { operation_type: string; object_name: string }): boolean {
  if (isTaxOperation(op)) return true;
  if (op.operation_type === 'Возвращено главой' && op.object_name === TAX_OBJECT_NAME) {
    return true;
  }
  return false;
}

export function getOriginalOwner(
  op: { operation_type: string; object_name: string; nick: string; quantity: number; date: string },
  allOperations: { nick: string; object_name: string; quantity: number; date: string }[]
): string {
  if (op.operation_type === 'Возвращено главой' && op.quantity > 0) {
    const sameResource = allOperations.filter(
      o => o.object_name === op.object_name && o.quantity < 0
    );
    const sameResourceSorted = sameResource.sort((a, b) => b.date.localeCompare(a.date));
    const original = sameResourceSorted[0];
    return original ? original.nick : op.nick;
  }
  return op.nick;
}
