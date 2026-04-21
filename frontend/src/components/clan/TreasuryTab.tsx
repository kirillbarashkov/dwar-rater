import { useState, useEffect, useMemo, useCallback } from 'react';
import { getTreasuryOperations } from '../../api/clanInfo';
import type { TreasuryOperationData } from '../../types/clanInfo';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import {
  TREASURY_WEB_URL,
  MONTHS_RU,
  PERIOD_OPTIONS,
  PAGE_SIZE_OPTIONS,
  SORT_KEYS,
  SORT_KEY_LABELS,
  parseDate,
  formatDateKey,
  getMonthDays,
  type PeriodType,
  type SortKey,
  type MonthDay,
} from '../../utils/treasury';
import './TreasuryTab.css';

interface TreasuryTabProps {
  clanId: number;
}

const INITIAL_FILTERS = {
  searchNick: '',
  searchType: '',
  searchObject: '',
  filterPeriod: 'all' as PeriodType,
  rangeStart: '',
  rangeEnd: '',
  selectedDate: null as string | null,
};

export function TreasuryTab({ clanId }: TreasuryTabProps) {
  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [sortConfig, setSortConfig] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({
    key: 'date',
    dir: 'desc',
  });
  const [pageSize, setPageSize] = useState(20);
  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth() + 1);

  const { searchNick, searchType, searchObject, filterPeriod, rangeStart, rangeEnd, selectedDate } = filters;

  const loadOperations = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getTreasuryOperations(clanId);
      setOperations(data);
    } catch {
      setOperations([]);
    } finally {
      setIsLoading(false);
    }
  }, [clanId]);

  useEffect(() => {
    loadOperations();
  }, [loadOperations]);

  const handleAnalyze = (nick: string) => {
    window.open(`${TREASURY_WEB_URL}?nick=${encodeURIComponent(nick)}`, '_blank');
  };

  const handleSort = (key: SortKey) => {
    setSortConfig((prev) => ({
      key,
      dir: prev.key === key && prev.dir === 'asc' ? 'desc' : 'asc',
    }));
  };

  const handleClearFilters = () => {
    setFilters(INITIAL_FILTERS);
  };

  const handlePeriodChange = (value: PeriodType) => {
    setFilters((prev) => ({ ...prev, filterPeriod: value, selectedDate: null }));
  };

  const handleDateSelect = (dateKey: string, hasData: boolean) => {
    if (!hasData) return;
    setFilters((prev) => ({
      ...prev,
      selectedDate: prev.selectedDate === dateKey ? null : dateKey,
    }));
  };

  const handlePrevMonth = () => {
    const newMonth = currentMonth === 1 ? 12 : currentMonth - 1;
    const newYear = currentMonth === 1 ? currentYear - 1 : currentYear;
    setCurrentYear(newYear);
    setCurrentMonth(newMonth);
    setFilters((prev) => ({ ...prev, selectedDate: null }));
  };

  const handleNextMonth = () => {
    const newMonth = currentMonth === 12 ? 1 : currentMonth + 1;
    const newYear = currentMonth === 12 ? currentYear + 1 : currentYear;
    setCurrentYear(newYear);
    setCurrentMonth(newMonth);
    setFilters((prev) => ({ ...prev, selectedDate: null }));
  };

  const uniqueTypes = useMemo(() => {
    const types = new Set(operations.map((op) => op.operation_type));
    return Array.from(types).sort();
  }, [operations]);

  const dateSet = useMemo(() => {
    const set = new Set<string>();
    for (const op of operations) {
      const parsed = parseDate(op.date);
      if (parsed) {
        set.add(formatDateKey(parsed.day, parsed.month, parsed.year));
      }
    }
    return set;
  }, [operations]);

  const monthDays = useMemo((): MonthDay[] => {
    return getMonthDays(currentYear, currentMonth).map((d) => ({
      ...d,
      hasData: dateSet.has(d.dateKey),
    }));
  }, [currentYear, currentMonth, dateSet]);

  const filtered = useMemo(() => {
    let result = [...operations];

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

    if (selectedDate) {
      result = result.filter((op) => {
        const parsed = parseDate(op.date);
        if (!parsed) return false;
        return formatDateKey(parsed.day, parsed.month, parsed.year) === selectedDate;
      });
    }

    return result;
  }, [operations, searchNick, searchType, searchObject, filterPeriod, rangeStart, rangeEnd, currentYear, currentMonth, selectedDate]);

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

  useEffect(() => {
    setCurrentPage(1);
  }, [pageSize, filtered.length, searchNick, searchType, searchObject, filterPeriod, selectedDate]);

  const getSortIndicator = (key: SortKey) => {
    if (sortConfig.key !== key) return null;
    return sortConfig.dir === 'asc' ? ' ↑' : ' ↓';
  };

  const hasActiveFilters =
    searchNick || searchType || searchObject || filterPeriod !== 'all' || selectedDate;

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="treasury-tab">
      <header className="treasury-header">
        <h2 className="treasury-title">Казна</h2>
      </header>

      {operations.length === 0 ? (
        <div className="treasury-empty">
          <p>Нет данных о казне.</p>
          <p>Используйте вкладку &quot;Импорт&quot; для добавления данных.</p>
        </div>
      ) : operations.length > 0 ? (
        <>
          <section className="treasury-filters" aria-label="Фильтры">
            <div className="treasury-filter-row">
              <div className="treasury-filter-group">
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
                  <label className="treasury-date-range">
                    <span className="treasury-date-label">От</span>
                    <input
                      type="date"
                      className="treasury-date-input"
                      value={rangeStart}
                      onChange={(e) => setFilters((prev) => ({ ...prev, rangeStart: e.target.value }))}
                      aria-label="Дата начала"
                    />
                  </label>
                  <span className="treasury-date-separator" aria-hidden="true">—</span>
                  <label className="treasury-date-range">
                    <span className="treasury-date-label">До</span>
                    <input
                      type="date"
                      className="treasury-date-input"
                      value={rangeEnd}
                      onChange={(e) => setFilters((prev) => ({ ...prev, rangeEnd: e.target.value }))}
                      aria-label="Дата окончания"
                    />
                  </label>
                </>
              )}

              <div className="treasury-filter-group">
                <input
                  type="text"
                  placeholder="Игрок..."
                  value={searchNick}
                  onChange={(e) => setFilters((prev) => ({ ...prev, searchNick: e.target.value }))}
                  className="treasury-search"
                  aria-label="Поиск по игроку"
                />
              </div>

              <div className="treasury-filter-group">
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

              <div className="treasury-filter-group">
                <input
                  type="text"
                  placeholder="Объект..."
                  value={searchObject}
                  onChange={(e) => setFilters((prev) => ({ ...prev, searchObject: e.target.value }))}
                  className="treasury-search"
                  aria-label="Поиск по объекту"
                />
              </div>

              {hasActiveFilters && (
                <button
                  className="treasury-clear-filters"
                  onClick={handleClearFilters}
                  aria-label="Очистить фильтры"
                  type="button"
                >
                  ×
                </button>
              )}
            </div>

            <nav className="treasury-month-nav" aria-label="Навигация по месяцам">
              <button onClick={handlePrevMonth} aria-label="Предыдущий месяц" type="button">
                ←
              </button>
              <span className="treasury-month-label" aria-live="polite">
                {MONTHS_RU[currentMonth]} {currentYear}
              </span>
              <button onClick={handleNextMonth} aria-label="Следующий месяц" type="button">
                →
              </button>
            </nav>

            <div className="treasury-month-strip" role="list" aria-label="Календарь дней">
              {monthDays.map(({ day, dateKey, hasData }) => (
                <div
                  key={dateKey}
                  className={`treasury-month-day ${hasData ? 'has-data' : ''} ${
                    selectedDate === dateKey ? 'selected' : ''
                  }`}
                  onClick={() => handleDateSelect(dateKey, hasData)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleDateSelect(dateKey, hasData);
                    }
                  }}
                  tabIndex={hasData ? 0 : -1}
                  role="button"
                  aria-label={`${day} ${MONTHS_RU[currentMonth]} ${hasData ? 'есть данные' : 'нет данных'}`}
                  aria-pressed={selectedDate === dateKey}
                >
                  {day}
                </div>
              ))}
            </div>
          </section>

          <div className="treasury-table-container">
            <table className="treasury-table" aria-label="Операции казны">
              <thead>
                <tr>
                  <th scope="col" className="treasury-number">#</th>
                  {SORT_KEYS.map((key) => (
                    <th
                      key={key}
                      scope="col"
                      className={key === 'quantity' ? 'treasury-sortable treasury-col-quantity' : 'treasury-sortable'}
                      onClick={() => handleSort(key)}
                      aria-sort={
                        sortConfig.key === key
                          ? sortConfig.dir === 'asc'
                            ? 'ascending'
                            : 'descending'
                          : 'none'
                      }
                    >
                      {SORT_KEY_LABELS[key]}
                      {getSortIndicator(key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paginated.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="treasury-no-data">
                      Нет данных за выбранный период
                    </td>
                  </tr>
                ) : (
                  paginated.map((op, index) => (
                    <tr key={op.id}>
                      <td className="treasury-number">
                        {(currentPage - 1) * pageSize + index + 1}
                      </td>
                      <td className="treasury-date">{op.date}</td>
                      <td className="treasury-nick treasury-link" onClick={() => handleAnalyze(op.nick)}>
                        {op.nick}
                      </td>
                      <td className="treasury-type">{op.operation_type}</td>
                      <td className="treasury-object">{op.object_name}</td>
                      <td
                        className={`treasury-quantity ${op.quantity >= 0 ? 'positive' : 'negative'}`}
                      >
                        {op.quantity >= 0 ? '+' : ''}
                        {op.quantity.toLocaleString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="treasury-pagination" role="navigation" aria-label="Пагинация">
            <div className="treasury-pagination-info" aria-live="polite">
              Показано {paginated.length} из {sorted.length} записей
            </div>
            <div className="treasury-pagination-controls">
              <label htmlFor="page-size-select" className="visually-hidden">
                Количество записей на странице
              </label>
              <select
                id="page-size-select"
                className="treasury-page-size"
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
                className="treasury-page-btn"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(1)}
                aria-label="Первая страница"
                type="button"
              >
                ««
              </button>
              <button
                className="treasury-page-btn"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => p - 1)}
                aria-label="Предыдущая страница"
                type="button"
              >
                «
              </button>
              <span className="treasury-page-current" aria-current="page">
                {currentPage} / {totalPages}
              </span>
              <button
                className="treasury-page-btn"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
                aria-label="Следующая страница"
                type="button"
              >
                »
              </button>
              <button
                className="treasury-page-btn"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(totalPages)}
                aria-label="Последняя страница"
                type="button"
              >
                »»
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
