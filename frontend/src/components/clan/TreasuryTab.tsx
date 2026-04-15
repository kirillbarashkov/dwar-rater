import { useState, useEffect, useMemo, useCallback } from 'react';
import { getTreasuryOperations, importTreasuryOperations } from '../../api/clanInfo';
import type { TreasuryOperationData } from '../../types/clanInfo';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { Button } from '../ui/Button';
import './TreasuryTab.css';

interface TreasuryTabProps {
  clanId: number;
}

function parseTreasuryOperations(html: string): Omit<TreasuryOperationData, 'id'>[] {
  const operations: Omit<TreasuryOperationData, 'id'>[] = [];
  const seen = new Set<string>();
  
  const rowRegex = /<tr\s*class="[^"]*">(.*?)<\/tr>/gs;
  const dateRegex = /(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})/;
  const nickRegex = /userToTag\(\s*'([^']+)'\s*\)/;
  
  function cleanHtml(html: string): string {
    return html.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').trim();
  }
  
  let rowMatch;
  while ((rowMatch = rowRegex.exec(html)) !== null) {
    const rowHtml = rowMatch[1];
    const cells: string[] = [];
    const cellStyles: string[] = [];
    
    let tdMatch;
    const tdRegex = /<td[^>]*class="brd-all p6h"([^>]*)>(.*?)<\/td>/gs;
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
    
    let quantity = 0;
    let direction = 1;
    
    const isGreen = /color:\s*green/i.test(cell5Style);
    const isRed = /color:\s*red/i.test(cell5Style);
    
    if (isGreen) {
      direction = 1;
      const numMatch = cleanCell5.match(/(-?\d+)/);
      if (numMatch) {
        quantity = Math.abs(parseInt(numMatch[1], 10));
      }
    } else if (isRed) {
      direction = -1;
      const numMatch = cleanCell5.match(/(-?\d+)/);
      if (numMatch) {
        quantity = Math.abs(parseInt(numMatch[1], 10));
      }
    }
    
    const key = `${date}|${nick}|${operation_type}|${objectName}|${quantity}`;
    if (seen.has(key)) continue;
    seen.add(key);
    
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

function parseDate(dateStr: string): { day: number; month: number; year: number } | null {
  const match = dateStr.match(/(\d{2})\.(\d{2})\.(\d{4})/);
  if (!match) return null;
  return {
    day: parseInt(match[1], 10),
    month: parseInt(match[2], 10),
    year: parseInt(match[3], 10)
  };
}

function formatDateKey(day: number, month: number, year: number): string {
  return `${day.toString().padStart(2, '0')}.${month.toString().padStart(2, '0')}.${year}`;
}

function getMonthDays(year: number, month: number): { day: number; dateKey: string; hasData: boolean }[] {
  const daysInMonth = new Date(year, month, 0).getDate();
  const result = [];
  for (let d = 1; d <= daysInMonth; d++) {
    result.push({
      day: d,
      dateKey: formatDateKey(d, month, year),
      hasData: false
    });
  }
  return result;
}

const MONTHS = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

export function TreasuryTab({ clanId }: TreasuryTabProps) {
  const [operations, setOperations] = useState<TreasuryOperationData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [pastedHtml, setPastedHtml] = useState('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [sortConfig, setSortConfig] = useState<{ key: string; dir: 'asc' | 'desc' }>({ key: 'date', dir: 'desc' });
  const [pageSize, setPageSize] = useState(20);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchNick, setSearchNick] = useState('');
  const [searchType, setSearchType] = useState('');
  const [searchObject, setSearchObject] = useState('');
  const [filterPeriod, setFilterPeriod] = useState<'all' | 'today' | 'month' | 'range'>('all');
  const [rangeStart, setRangeStart] = useState('');
  const [rangeEnd, setRangeEnd] = useState('');
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

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

  const handleImport = async () => {
    if (!pastedHtml.trim()) {
      setMessage({ type: 'error', text: 'Вставьте HTML код страницы' });
      return;
    }
    
    setIsImporting(true);
    setMessage(null);
    
    try {
      const parsed = parseTreasuryOperations(pastedHtml);
      
      if (parsed.length === 0) {
        setMessage({ type: 'error', text: 'Не удалось найти операции. Убедитесь, что скопировали HTML со страницы со таблицей.' });
        setIsImporting(false);
        return;
      }
      
      const result = await importTreasuryOperations(clanId, parsed);
      
      if (result.success) {
        setMessage({ type: 'success', text: `Импортировано ${result.imported}, обновлено ${result.updated} операций` });
        setPastedHtml('');
        setShowImport(false);
        await loadOperations();
      } else {
        setMessage({ type: 'error', text: result.message || 'Ошибка при импорте' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: `Ошибка при импорте: ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setIsImporting(false);
    }
  };

  const handleAnalyze = (nick: string) => {
    const url = `https://w1.dwar.ru/user_info.php?nick=${encodeURIComponent(nick)}`;
    window.open(url, '_blank');
  };

  const handleSort = (key: string) => {
    setSortConfig((prev) => ({
      key,
      dir: prev.key === key && prev.dir === 'asc' ? 'desc' : 'asc',
    }));
  };

  const uniqueTypes = useMemo(() => {
    const types = new Set(operations.map(op => op.operation_type));
    return Array.from(types).sort();
  }, [operations]);

  const dateSet = useMemo(() => {
    const set = new Set<string>();
    operations.forEach(op => {
      const parsed = parseDate(op.date);
      if (parsed) {
        set.add(formatDateKey(parsed.day, parsed.month, parsed.year));
      }
    });
    return set;
  }, [operations]);

  const monthDays = useMemo(() => {
    return getMonthDays(currentYear, currentMonth).map(d => ({
      ...d,
      hasData: dateSet.has(d.dateKey)
    }));
  }, [currentYear, currentMonth, dateSet]);

  const filtered = useMemo(() => {
    let result = [...operations];
    
    if (searchNick) {
      result = result.filter(op => op.nick.toLowerCase().includes(searchNick.toLowerCase()));
    }
    if (searchType) {
      result = result.filter(op => op.operation_type === searchType);
    }
    if (searchObject) {
      result = result.filter(op => op.object_name.toLowerCase().includes(searchObject.toLowerCase()));
    }
    
    const now = new Date();
    const today = formatDateKey(now.getDate(), now.getMonth() + 1, now.getFullYear());
    
    switch (filterPeriod) {
      case 'today':
        result = result.filter(op => {
          const parsed = parseDate(op.date);
          if (!parsed) return false;
          const key = formatDateKey(parsed.day, parsed.month, parsed.year);
          return key === today;
        });
        break;
      case 'month':
        result = result.filter(op => {
          const parsed = parseDate(op.date);
          if (!parsed) return false;
          return parsed.year === currentYear && parsed.month === currentMonth;
        });
        break;
      case 'range':
        if (rangeStart) {
          result = result.filter(op => op.date >= rangeStart);
        }
        if (rangeEnd) {
          result = result.filter(op => op.date <= rangeEnd);
        }
        break;
    }
    
    if (selectedDate) {
      result = result.filter(op => {
        const parsed = parseDate(op.date);
        if (!parsed) return false;
        const key = formatDateKey(parsed.day, parsed.month, parsed.year);
        return key === selectedDate;
      });
    }
    
    return result;
  }, [operations, searchNick, searchType, searchObject, filterPeriod, rangeStart, rangeEnd, currentYear, currentMonth, selectedDate]);

  const sorted = useMemo(() => {
    const result = [...filtered];
    result.sort((a, b) => {
      let aVal: string | number = '';
      let bVal: string | number = '';
      
      switch (sortConfig.key) {
        case 'date':
          aVal = a.date;
          bVal = b.date;
          break;
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
        return sortConfig.dir === 'asc' ? aVal - bVal : bVal - aVal;
      }
      
      return sortConfig.dir === 'asc' ? String(aVal).localeCompare(String(bVal)) : String(bVal).localeCompare(String(aVal));
    });
    return result;
  }, [filtered, sortConfig]);

  const totalPages = Math.ceil(sorted.length / pageSize);
  const paginated = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  useEffect(() => {
    setCurrentPage(1);
  }, [pageSize, filtered.length, searchNick, searchType, searchObject, filterPeriod, selectedDate]);

  const getSortIndicator = (key: string) => {
    if (sortConfig.key !== key) return '';
    return sortConfig.dir === 'asc' ? ' ↑' : ' ↓';
  };

  const handlePrevMonth = () => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear(y => y - 1);
    } else {
      setCurrentMonth(m => m - 1);
    }
    setSelectedDate(null);
  };

  const handleNextMonth = () => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear(y => y + 1);
    } else {
      setCurrentMonth(m => m + 1);
    }
    setSelectedDate(null);
  };

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="treasury-tab">
      <div className="treasury-header">
        <h3 className="treasury-title">💰 Операции казны</h3>
        <Button
          variant="secondary"
          size="small"
          onClick={() => setShowImport(!showImport)}
        >
          {showImport ? 'Отмена' : '📋 Импорт из HTML'}
        </Button>
      </div>

      {message && (
        <div className={`treasury-message treasury-message-${message.type}`}>
          {message.text}
        </div>
      )}

      {showImport && (
        <div className="treasury-import">
          <div className="treasury-import-instructions">
            <h4>Как скопировать HTML:</h4>
            <ol>
              <li>Откройте страницу <a href="https://w1.dwar.ru/clan_management.php?f=1&mode=clancell&submode=report" target="_blank" rel="noopener noreferrer">Операции казны</a> в браузере</li>
              <li>Нажмите правую кнопку мыши → "Просмотр кода страницы" (или Ctrl+U)</li>
              <li>Выделите весь код (Ctrl+A) и скопируйте (Ctrl+C)</li>
              <li>Вставьте в поле ниже (Ctrl+V)</li>
            </ol>
          </div>
          <textarea
            className="treasury-html-input"
            value={pastedHtml}
            onChange={(e) => setPastedHtml(e.target.value)}
            placeholder="Вставьте HTML код страницы сюда..."
            rows={10}
          />
          <Button
            variant="primary"
            onClick={handleImport}
            disabled={isImporting || !pastedHtml.trim()}
          >
            {isImporting ? 'Импорт...' : 'Импортировать'}
          </Button>
        </div>
      )}

      {operations.length === 0 && !showImport ? (
        <div className="treasury-empty">
          <p>Нет данных о казне.</p>
          <p>Нажмите "Импорт из HTML" для добавления данных.</p>
        </div>
      ) : operations.length > 0 ? (
        <>
          <div className="treasury-filters">
            <div className="treasury-filter-row">
              <div className="treasury-filter-group">
                <label>Период:</label>
                <select value={filterPeriod} onChange={(e) => { setFilterPeriod(e.target.value as 'all' | 'today' | 'month' | 'range'); setSelectedDate(null); }}>
                  <option value="all">Все</option>
                  <option value="today">Сегодня</option>
                  <option value="month">Текущий месяц</option>
                  <option value="range">Диапазон</option>
                </select>
              </div>
              
              {filterPeriod === 'range' && (
                <>
                  <input
                    type="date"
                    className="treasury-date-input"
                    value={rangeStart}
                    onChange={(e) => setRangeStart(e.target.value)}
                    placeholder="От"
                  />
                  <span>—</span>
                  <input
                    type="date"
                    className="treasury-date-input"
                    value={rangeEnd}
                    onChange={(e) => setRangeEnd(e.target.value)}
                    placeholder="До"
                  />
                </>
              )}
              
              <div className="treasury-filter-group">
                <input
                  type="text"
                  placeholder="Игрок..."
                  value={searchNick}
                  onChange={(e) => setSearchNick(e.target.value)}
                  className="treasury-search"
                />
              </div>
              
              <div className="treasury-filter-group">
                <select value={searchType} onChange={(e) => setSearchType(e.target.value)}>
                  <option value="">Все типы</option>
                  {uniqueTypes.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              
              <div className="treasury-filter-group">
                <input
                  type="text"
                  placeholder="Объект..."
                  value={searchObject}
                  onChange={(e) => setSearchObject(e.target.value)}
                  className="treasury-search"
                />
              </div>
              
              {(searchNick || searchType || searchObject || filterPeriod !== 'all' || selectedDate) && (
                <button className="treasury-clear-filters" onClick={() => {
                  setSearchNick('');
                  setSearchType('');
                  setSearchObject('');
                  setFilterPeriod('all');
                  setSelectedDate(null);
                }}>
                  ×
                </button>
              )}
            </div>
            
            <div className="treasury-month-nav">
              <button onClick={handlePrevMonth}>←</button>
              <span className="treasury-month-label">{MONTHS[currentMonth]} {currentYear}</span>
              <button onClick={handleNextMonth}>→</button>
            </div>
            
            <div className="treasury-month-strip">
              {monthDays.map(({ day, dateKey, hasData }) => (
                <div
                  key={dateKey}
                  className={`treasury-month-day ${hasData ? 'has-data' : ''} ${selectedDate === dateKey ? 'selected' : ''}`}
                  onClick={() => hasData ? setSelectedDate(selectedDate === dateKey ? null : dateKey) : undefined}
                  title={hasData ? dateKey : 'Нет данных'}
                >
                  {day}
                </div>
              ))}
            </div>
          </div>

          <div className="treasury-table-container">
            <table className="treasury-table">
              <thead>
                <tr>
                  <th className="treasury-number">#</th>
                  <th className="treasury-sortable" onClick={() => handleSort('date')}>
                    Дата{getSortIndicator('date')}
                  </th>
                  <th className="treasury-sortable" onClick={() => handleSort('nick')}>
                    Игрок{getSortIndicator('nick')}
                  </th>
                  <th className="treasury-sortable" onClick={() => handleSort('operation_type')}>
                    Тип{getSortIndicator('operation_type')}
                  </th>
                  <th className="treasury-sortable" onClick={() => handleSort('object_name')}>
                    Объект{getSortIndicator('object_name')}
                  </th>
                  <th className="treasury-sortable treasury-col-quantity" onClick={() => handleSort('quantity')}>
                    Кол-во{getSortIndicator('quantity')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {paginated.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="treasury-no-data">Нет данных за выбранный период</td>
                  </tr>
                ) : paginated.map((op, index) => (
                  <tr key={op.id}>
                    <td className="treasury-number">{(currentPage - 1) * pageSize + index + 1}</td>
                    <td className="treasury-date">{op.date}</td>
                    <td
                      className="treasury-nick treasury-link"
                      onClick={() => handleAnalyze(op.nick)}
                    >
                      {op.nick}
                    </td>
                    <td className="treasury-type">{op.operation_type}</td>
                    <td className="treasury-object">{op.object_name}</td>
                    <td className={`treasury-quantity ${op.quantity >= 0 ? 'positive' : 'negative'}`}>
                      {op.quantity >= 0 ? '+' : ''}{op.quantity.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="treasury-pagination">
            <div className="treasury-pagination-info">
              Показано {paginated.length} из {sorted.length} записей
            </div>
            <div className="treasury-pagination-controls">
              <select
                className="treasury-page-size"
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
              <button
                className="treasury-page-btn"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(1)}
              >
                ««
              </button>
              <button
                className="treasury-page-btn"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => p - 1)}
              >
                «
              </button>
              <span className="treasury-page-current">
                {currentPage} / {totalPages}
              </span>
              <button
                className="treasury-page-btn"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
              >
                »
              </button>
              <button
                className="treasury-page-btn"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(totalPages)}
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