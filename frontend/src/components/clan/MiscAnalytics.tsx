import { useMemo, useState } from 'react';
import type { TreasuryOperationData } from '../../types/clanInfo';
import { parseDate, formatDateKey, isTaxOperation, isTalentOperation } from '../../utils/treasury';
import './MiscAnalytics.css';

interface MiscAnalyticsProps {
  operations: TreasuryOperationData[];
}

type PeriodType = 'all' | 'today' | 'month' | 'range';

const PERIOD_OPTIONS: { value: PeriodType; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'today', label: 'Сегодня' },
  { value: 'month', label: 'Текущий месяц' },
  { value: 'range', label: 'Диапазон' },
];

const PAGE_SIZE_OPTIONS = [20, 50, 100];

type SortKey = 'date' | 'nick' | 'operation_type' | 'object_name' | 'quantity';
type SortDirection = 'asc' | 'desc';

const SORT_KEY_LABELS: Record<SortKey, string> = {
  date: 'Дата',
  nick: 'Игрок',
  operation_type: 'Тип',
  object_name: 'Объект',
  quantity: 'Кол-во',
};

const INITIAL_FILTERS = {
  searchNick: '',
  searchType: '',
  searchObject: '',
  filterPeriod: 'all' as PeriodType,
  rangeStart: '',
  rangeEnd: '',
};

export function MiscAnalytics({ operations }: MiscAnalyticsProps) {
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth() + 1);
  const [sortConfig, setSortConfig] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({
    key: 'date',
    dir: 'desc',
  });
  const [pageSize, setPageSize] = useState(20);
  const [currentPage, setCurrentPage] = useState(1);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  const { searchNick, searchType, searchObject, filterPeriod, rangeStart, rangeEnd } = filters;

  const miscOperations = useMemo(() => {
    return operations.filter(op => {
      if (isTaxOperation(op)) return false;
      if (isTalentOperation(op)) return false;
      return true;
    });
  }, [operations]);

  const uniqueTypes = useMemo(() => {
    const types = new Set(miscOperations.map((op) => op.operation_type));
    return Array.from(types).sort();
  }, [miscOperations]);

  const uniqueObjects = useMemo(() => {
    const objects = new Set(miscOperations.map((op) => op.object_name));
    return Array.from(objects).sort();
  }, [miscOperations]);

  const filtered = useMemo(() => {
    let result = [...miscOperations];

    if (searchNick) {
      const nickLower = searchNick.toLowerCase();
      result = result.filter((op) => op.nick.toLowerCase().includes(nickLower));
    }
    if (searchType) {
      result = result.filter((op) => op.operation_type === searchType);
    }
    if (searchObject) {
      const objLower = searchObject.toLowerCase();
      result = result.filter((op) => op.object_name.toLowerCase().includes(objLower));
    }

    const now = new Date();
    const today = formatDateKey(now.getDate(), now.getMonth() + 1, now.getFullYear());

    switch (filterPeriod) {
      case 'today':
        result = result.filter((op) => {
          const parsed = parseDate(op.date);
          if (!parsed) return false;
          return formatDateKey(parsed.day, parsed.month, parsed.year) === today;
        });
        break;
      case 'month':
        result = result.filter((op) => {
          const parsed = parseDate(op.date);
          if (!parsed) return false;
          return parsed.year === currentYear && parsed.month === currentMonth;
        });
        break;
      case 'range':
        if (rangeStart) {
          const startParts = rangeStart.split('-').map(Number);
          const startDate = new Date(startParts[0], startParts[1] - 1, startParts[2]);
          result = result.filter((op) => {
            const parsed = parseDate(op.date);
            if (!parsed) return false;
            const opDate = new Date(parsed.year, parsed.month - 1, parsed.day);
            return opDate >= startDate;
          });
        }
        if (rangeEnd) {
          const endParts = rangeEnd.split('-').map(Number);
          const endDate = new Date(endParts[0], endParts[1] - 1, endParts[2]);
          endDate.setHours(23, 59, 59);
          result = result.filter((op) => {
            const parsed = parseDate(op.date);
            if (!parsed) return false;
            const opDate = new Date(parsed.year, parsed.month - 1, parsed.day);
            return opDate <= endDate;
          });
        }
        break;
    }

    return result;
  }, [miscOperations, searchNick, searchType, searchObject, filterPeriod, rangeStart, rangeEnd, currentYear, currentMonth]);

  const sorted = useMemo(() => {
    const result = [...filtered];
    const { key, dir } = sortConfig;

    result.sort((a, b) => {
      let aVal: string | number = '';
      let bVal: string | number = '';

      switch (key) {
        case 'date': {
          const parseSortDate = (dateStr: string): Date => {
            const [dmy, time] = dateStr.split(' ');
            const [day, month, year] = dmy.split('.').map(Number);
            const [hours, minutes] = time ? time.split(':').map(Number) : [0, 0];
            return new Date(year, month - 1, day, hours, minutes);
          };
          aVal = parseSortDate(a.date).getTime();
          bVal = parseSortDate(b.date).getTime();
          return dir === 'asc' ? Number(aVal) - Number(bVal) : Number(bVal) - Number(aVal);
        }
        case 'nick':
          aVal = a.nick.toLowerCase();
          bVal = b.nick.toLowerCase();
          break;
        case 'operation_type':
          aVal = a.operation_type.toLowerCase();
          bVal = b.operation_type.toLowerCase();
          break;
        case 'object_name':
          aVal = a.object_name.toLowerCase();
          bVal = b.object_name.toLowerCase();
          break;
        case 'quantity':
          aVal = a.quantity;
          bVal = b.quantity;
          break;
      }

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return dir === 'asc' ? aVal - bVal : bVal - aVal;
      }

      return dir === 'asc' ? String(aVal).localeCompare(String(bVal)) : String(bVal).localeCompare(String(aVal));
    });

    return result;
  }, [filtered, sortConfig]);

  const totalPages = Math.ceil(sorted.length / pageSize);
  const paginated = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const handleSort = (key: SortKey) => {
    setSortConfig((prev) => ({
      key,
      dir: prev.key === key && prev.dir === 'asc' ? 'desc' : 'asc',
    }));
  };

  const handlePeriodChange = (value: PeriodType) => {
    setFilters((prev) => ({ ...prev, filterPeriod: value }));
  };

  const handleClearFilters = () => {
    setFilters(INITIAL_FILTERS);
  };

  const handlePrevMonth = () => {
    const newMonth = currentMonth === 1 ? 12 : currentMonth - 1;
    const newYear = currentMonth === 1 ? currentYear - 1 : currentYear;
    setCurrentYear(newYear);
    setCurrentMonth(newMonth);
  };

  const handleNextMonth = () => {
    const newMonth = currentMonth === 12 ? 1 : currentMonth + 1;
    const newYear = currentMonth === 12 ? currentYear + 1 : currentYear;
    setCurrentYear(newYear);
    setCurrentMonth(newMonth);
  };

  const getSortIndicator = (key: SortKey) => {
    if (sortConfig.key !== key) return null;
    return sortConfig.dir === 'asc' ? ' ↑' : ' ↓';
  };

  const hasActiveFilters =
    searchNick || searchType || searchObject || filterPeriod !== 'all';

  const handleCopyTable = async () => {
    if (paginated.length === 0) return;

    const headers = ['Дата', 'Игрок', 'Тип', 'Объект', 'Кол-во'];
    const rows = paginated.map((op) => [
      op.date,
      op.nick,
      op.operation_type,
      op.object_name,
      op.quantity >= 0 ? `+${op.quantity}` : op.quantity,
    ].join('\t')).join('\n');

    const text = [headers.join('\t'), rows].join('\n');

    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus('Скопировано!');
      setTimeout(() => setCopyStatus(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
      setCopyStatus('Ошибка копирования');
      setTimeout(() => setCopyStatus(null), 2000);
    }
  };

  const MONTHS_RU = [
    '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
  ];

  return (
    <div className="misc-analytics">
      <header className="misc-header">
        <h2 className="misc-title">Прочее</h2>
        <div className="misc-header-actions">
          {copyStatus && <span className="misc-copy-status">{copyStatus}</span>}
          <button
            className="misc-copy-btn"
            onClick={handleCopyTable}
            title="Копировать таблицу"
            disabled={paginated.length === 0}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
        </div>
      </header>

      <section className="misc-filters" aria-label="Фильтры">
        <div className="misc-filter-row">
          <div className="misc-filter-group">
            <label htmlFor="period-select">Период:</label>
            <select
              id="period-select"
              value={filterPeriod}
              onChange={(e) => handlePeriodChange(e.target.value as PeriodType)}
            >
              {PERIOD_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {filterPeriod === 'range' && (
            <>
              <label className="misc-date-range">
                <span className="misc-date-label">От</span>
                <input
                  type="date"
                  className="misc-date-input"
                  value={rangeStart}
                  onChange={(e) => setFilters((prev) => ({ ...prev, rangeStart: e.target.value }))}
                  aria-label="Дата начала"
                />
              </label>
              <span className="misc-date-separator" aria-hidden="true">—</span>
              <label className="misc-date-range">
                <span className="misc-date-label">До</span>
                <input
                  type="date"
                  className="misc-date-input"
                  value={rangeEnd}
                  onChange={(e) => setFilters((prev) => ({ ...prev, rangeEnd: e.target.value }))}
                  aria-label="Дата окончания"
                />
              </label>
            </>
          )}

          {filterPeriod === 'month' && (
            <nav className="misc-month-nav" aria-label="Навигация по месяцам">
              <button onClick={handlePrevMonth} aria-label="Предыдущий месяц" type="button">
                ←
              </button>
              <span className="misc-month-label">
                {MONTHS_RU[currentMonth]} {currentYear}
              </span>
              <button onClick={handleNextMonth} aria-label="Следующий месяц" type="button">
                →
              </button>
            </nav>
          )}

          <div className="misc-filter-group">
            <input
              type="text"
              placeholder="Игрок..."
              value={searchNick}
              onChange={(e) => setFilters((prev) => ({ ...prev, searchNick: e.target.value }))}
              className="misc-search"
              aria-label="Поиск по игроку"
            />
          </div>

          <div className="misc-filter-group">
            <select
              value={searchType}
              onChange={(e) => setFilters((prev) => ({ ...prev, searchType: e.target.value }))}
              aria-label="Фильтр по типу"
            >
              <option value="">Все типы</option>
              {uniqueTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="misc-filter-group">
            <select
              value={searchObject}
              onChange={(e) => setFilters((prev) => ({ ...prev, searchObject: e.target.value }))}
              aria-label="Фильтр по объекту"
            >
              <option value="">Все объекты</option>
              {uniqueObjects.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </div>

          {hasActiveFilters && (
            <button
              className="misc-clear-filters"
              onClick={handleClearFilters}
              aria-label="Очистить фильтры"
              type="button"
            >
              ×
            </button>
          )}
        </div>
      </section>

      <div className="misc-table-container">
        <table className="misc-table" aria-label="Операции">
          <thead>
            <tr>
              <th className="misc-sortable" onClick={() => handleSort('date')}>
                Дата {getSortIndicator('date')}
              </th>
              <th className="misc-sortable" onClick={() => handleSort('nick')}>
                Игрок {getSortIndicator('nick')}
              </th>
              <th className="misc-sortable" onClick={() => handleSort('operation_type')}>
                Тип {getSortIndicator('operation_type')}
              </th>
              <th className="misc-sortable" onClick={() => handleSort('object_name')}>
                Объект {getSortIndicator('object_name')}
              </th>
              <th className="misc-sortable misc-col-quantity" onClick={() => handleSort('quantity')}>
                Кол-во {getSortIndicator('quantity')}
              </th>
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={5} className="misc-no-data">
                  Нет данных за выбранный период
                </td>
              </tr>
            ) : (
              paginated.map((op, index) => (
                <tr key={op.id}>
                  <td className="misc-date">{op.date}</td>
                  <td className="misc-nick">{op.nick}</td>
                  <td className="misc-type">{op.operation_type}</td>
                  <td className="misc-object">{op.object_name}</td>
                  <td className={`misc-quantity ${op.quantity >= 0 ? 'positive' : 'negative'}`}>
                    {op.quantity >= 0 ? '+' : ''}
                    {op.quantity.toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="misc-pagination" role="navigation" aria-label="Пагинация">
        <div className="misc-pagination-info" aria-live="polite">
          Показано {paginated.length} из {sorted.length} записей
        </div>
        <div className="misc-pagination-controls">
          <select
            className="misc-page-size"
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
          <button
            className="misc-page-btn"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(1)}
            aria-label="Первая страница"
            type="button"
          >
            ««
          </button>
          <button
            className="misc-page-btn"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((p) => p - 1)}
            aria-label="Предыдущая страница"
            type="button"
          >
            «
          </button>
          <span className="misc-page-current" aria-current="page">
            {currentPage} / {totalPages}
          </span>
          <button
            className="misc-page-btn"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((p) => p + 1)}
            aria-label="Следующая страница"
            type="button"
          >
            »
          </button>
          <button
            className="misc-page-btn"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(totalPages)}
            aria-label="Последняя страница"
            type="button"
          >
            »»
          </button>
        </div>
      </div>
    </div>
  );
}
