import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import {
  getTreasuryOperations,
  importTreasuryOperations,
  saveTreasuryCookies,
  getTreasuryCookiesStatus,
  getTreasuryDateCoverage,
} from '../../api/clanInfo';
import type { TreasuryOperationData, DateCoverage } from '../../types/clanInfo';
import { Button } from '../ui/Button';
import { BackupPicker } from './BackupPicker';
import { parseTreasuryOperations, parseDate, TREASURY_CLAN_REPORT_URL, MONTHS_RU, type ParsedTreasuryOperation } from '../../utils/treasury';
import { MembershipImportTab } from './MembershipImportTab';
import './TreasuryImport.css';

interface TreasuryImportProps {
  clanId: number;
  onImportComplete?: () => void;
}

type SubTab = 'cookies' | 'import' | 'export' | 'membership';
type ImportSubTab = 'auto' | 'html';
type ParsedRow = ParsedTreasuryOperation;

export function TreasuryImport({ clanId, onImportComplete }: TreasuryImportProps) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('cookies');
  const [importSubTab, setImportSubTab] = useState<ImportSubTab>('auto');

  return (
    <div className="treasury-import-page">
      <header className="treasury-import-header">
        <h2 className="treasury-import-title">Казна</h2>
      </header>

      <div className="treasury-import-tabs">
        <button
          className={`treasury-import-tab-btn ${activeSubTab === 'cookies' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('cookies')}
        >
          Cookies
        </button>
        <button
          className={`treasury-import-tab-btn ${activeSubTab === 'import' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('import')}
        >
          Импорт данных
        </button>
        <button
          className={`treasury-import-tab-btn ${activeSubTab === 'export' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('export')}
        >
          Экспорт
        </button>
        <button
          className={`treasury-import-tab-btn ${activeSubTab === 'membership' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('membership')}
        >
          Состав клана
        </button>
      </div>

      {activeSubTab === 'cookies' && <CookiesTab clanId={clanId} />}

      {activeSubTab === 'import' && (
        <div className="treasury-import-subtabs">
          <div className="treasury-import-subtabs-bar">
            <button
              className={`treasury-import-subtab-btn ${importSubTab === 'auto' ? 'active' : ''}`}
              onClick={() => setImportSubTab('auto')}
            >
              Автоматический
            </button>
            <button
              className={`treasury-import-subtab-btn ${importSubTab === 'html' ? 'active' : ''}`}
              onClick={() => setImportSubTab('html')}
            >
              HTML данные
            </button>
          </div>
          {importSubTab === 'auto' && <ImportTab clanId={clanId} onImportComplete={onImportComplete} />}
          {importSubTab === 'html' && <HtmlImportTab clanId={clanId} onImportComplete={onImportComplete} />}
        </div>
      )}

      {activeSubTab === 'export' && <ExportTab clanId={clanId} />}
      {activeSubTab === 'membership' && <MembershipImportTab clanId={clanId} onImportComplete={onImportComplete} />}
    </div>
  );
}

interface ImportStatus {
  type: 'new' | 'updated' | 'same';
  existingRecord?: TreasuryOperationData;
  oldQuantity?: number;
}

interface CookieFieldDef {
  key: string;
  label: string;
  description: string;
  required: boolean;
  placeholder: string;
}

const COOKIE_FIELDS: CookieFieldDef[] = [
  { key: 'sess_sid', label: 'sess_sid', description: 'Session ID — идентификатор сессии', required: true, placeholder: 'b2838a768068bc4f...' },
  { key: 'sess_uid', label: 'sess_uid', description: 'User ID — идентификатор пользователя', required: true, placeholder: '2219483' },
  { key: 'sess_crc', label: 'sess_crc', description: 'Session CRC — контрольная сумма сессии', required: true, placeholder: '8596427e42ea7516...' },
  { key: 'sess_nn', label: 'sess_nn', description: 'Session number', required: true, placeholder: '3' },
  { key: 'sess_area_id', label: 'sess_area_id', description: 'ID зоны/сервера', required: true, placeholder: '302' },
  { key: 'sess_location', label: 'sess_location', description: 'Позиция в игре', required: true, placeholder: '301|302' },
  { key: 'mycom', label: 'mycom', description: 'Access token + refresh token', required: true, placeholder: 'access_token%3D...%26refresh_token%3D...' },
  { key: 'sstype', label: 'sstype', description: 'Тип сессии', required: true, placeholder: '18' },
];

function parseCookieValue(cookieString: string, key: string): string {
  const parts = cookieString.split(';');
  for (const part of parts) {
    const [k, ...vParts] = part.trim().split('=');
    if (k.trim() === key) {
      return vParts.join('=').trim();
    }
  }
  return '';
}

function buildCookieString(values: Record<string, string>): string {
  return Object.entries(values)
    .filter(([, v]) => v.trim().length > 0)
    .map(([k, v]) => `${k}=${v.trim()}`)
    .join('; ');
}

function CookieField({
  field,
  value,
  onChange,
  validationStatus,
}: {
  field: CookieFieldDef;
  value: string;
  onChange: (val: string) => void;
  validationStatus: 'ok' | 'missing' | 'empty';
}) {
  return (
    <div className="cookie-field">
      <div className="cookie-field-header">
        <label className="cookie-field-label">
          <code>{field.key}</code>
          {field.required && <span className="cookie-field-required">*</span>}
        </label>
        <span className={`cookie-field-status cookie-field-status-${validationStatus}`}>
          {validationStatus === 'ok' ? 'OK' : validationStatus === 'missing' ? '—' : 'Пусто'}
        </span>
      </div>
      <p className="cookie-field-desc">{field.description}</p>
      <input
        type="text"
        className="cookie-field-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={field.placeholder}
        autoComplete="off"
        spellCheck={false}
      />
    </div>
  );
}

function ImportTab({ clanId, onImportComplete }: { clanId: number; onImportComplete?: () => void }) {
  const [pastedHtml, setPastedHtml] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [importResult, setImportResult] = useState<{ imported: number; updated: number; skipped: number } | null>(null);

  const [dbOperations, setDbOperations] = useState<TreasuryOperationData[]>([]);
  const [dateCoverage, setDateCoverage] = useState<DateCoverage | null>(null);
  const [selectedStartDate, setSelectedStartDate] = useState<string | null>(null);
  const [selectedEndDate, setSelectedEndDate] = useState<string | null>(null);
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set());
  const [expandedMonths, setExpandedMonths] = useState<Set<string>>(new Set());

  const [cookieStatus, setCookieStatus] = useState<{ has_cookies: boolean; is_valid: boolean; updated_at?: string | null }>({ has_cookies: false, is_valid: false });
  const [showCookieEditor, setShowCookieEditor] = useState(false);
  const [cookieValues, setCookieValues] = useState<Record<string, string>>({});
  const [isSavingCookies, setIsSavingCookies] = useState(false);
  const [bulkCookieInput, setBulkCookieInput] = useState('');
  const [showBulkInput, setShowBulkInput] = useState(false);

  const [autoFetchOps, setAutoFetchOps] = useState<ParsedRow[]>([]);
  const [isAutoFetching, setIsAutoFetching] = useState(false);
  const [pageEstimate, setPageEstimate] = useState<{
    estimated_pages: number;
    start_page: number;
    end_page: number;
    total_pages: number;
    sample_dates: Record<string, string>;
  } | null>(null);
  const [isEstimating, setIsEstimating] = useState(false);
  const pageEstimateRef = useRef<typeof pageEstimate>(null);
  pageEstimateRef.current = pageEstimate;

  useEffect(() => {
    getTreasuryOperations(clanId).then(setDbOperations).catch(() => setDbOperations([]));
    loadDateCoverage();
  }, [clanId]);

  const loadDateCoverage = useCallback(() => {
    getTreasuryDateCoverage(clanId).then((data) => {
      setDateCoverage(data);
      if (data.latest_date) {
        setSelectedStartDate(data.latest_date);
        setSelectedEndDate(null);
      }
    }).catch(() => setDateCoverage(null));
  }, [clanId]);

  useEffect(() => {
    getTreasuryCookiesStatus(clanId).then(setCookieStatus).catch(() => setCookieStatus({ has_cookies: false, is_valid: false }));
  }, [clanId]);

  const refreshCookieStatus = useCallback(() => {
    getTreasuryCookiesStatus(clanId).then(setCookieStatus).catch(() => setCookieStatus({ has_cookies: false, is_valid: false }));
  }, [clanId]);

  const openCookieEditor = () => {
    setShowCookieEditor(true);
    setShowBulkInput(false);
    setCookieValues({});
    setBulkCookieInput('');
  };

  const handleParseBulkCookies = () => {
    const parsed: Record<string, string> = {};
    for (const field of COOKIE_FIELDS) {
      parsed[field.key] = parseCookieValue(bulkCookieInput, field.key);
    }
    setCookieValues(parsed);
    setShowBulkInput(false);
  };

  const handleSaveCookies = async () => {
    const cookieString = buildCookieString(cookieValues);
    if (!cookieString.trim()) {
      setMessage({ type: 'error', text: 'Заполните хотя бы одно поле cookies' });
      return;
    }

    const missingRequired = COOKIE_FIELDS.filter((f) => f.required && !cookieValues[f.key]?.trim());
    if (missingRequired.length > 0) {
      setMessage({ type: 'error', text: `Не заполнены обязательные поля: ${missingRequired.map((f) => f.key).join(', ')}` });
      return;
    }

    setIsSavingCookies(true);
    setMessage(null);
    try {
      const result = await saveTreasuryCookies(clanId, cookieString);
      if (result.success) {
        setMessage({ type: 'success', text: result.message });
        setShowCookieEditor(false);
        setCookieValues({});
        setBulkCookieInput('');
        refreshCookieStatus();
      } else {
        setMessage({ type: 'error', text: result.message || result.error || 'Ошибка сохранения cookies' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: `Ошибка: ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setIsSavingCookies(false);
    }
  };

  const [fetchProgress, setFetchProgress] = useState<{
    phase: 'counting' | 'fetching' | 'done' | 'error';
    totalPages: number;
    currentPage: number;
    totalOps: number;
    opsOnPage: number;
    elapsed: number;
    message: string;
  }>({ phase: 'counting', totalPages: 0, currentPage: 0, totalOps: 0, opsOnPage: 0, elapsed: 0, message: '' });
  const [eventSource, setEventSource] = useState<EventSource | null>(null);

  const cancelAutoFetch = useCallback(() => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }
    setIsAutoFetching(false);
    setFetchProgress((prev) => ({ ...prev, phase: 'error', message: 'Сбор отменён пользователем' }));
  }, [eventSource]);

  const estimatePages = useCallback(async () => {
    setIsEstimating(true);
    setPageEstimate(null);
    setMessage(null);
    try {
      const apiBase = import.meta.env.VITE_API_URL || window.location.origin;
      const token = localStorage.getItem('auth_token');
      const startDate = selectedStartDate || '01.01.2025';
      const res = await fetch(`${apiBase}/api/clan/${clanId}/treasury/estimate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          start_date: startDate,
          end_date: selectedEndDate || undefined,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setPageEstimate({
          estimated_pages: data.estimated_pages,
          start_page: data.start_page,
          end_page: data.end_page,
          total_pages: data.total_pages,
          sample_dates: data.sample_dates,
        });
      } else {
        setMessage({ type: 'error', text: data.message || data.error || 'Ошибка оценки' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: `Ошибка: ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setIsEstimating(false);
    }
  }, [clanId, selectedStartDate, selectedEndDate]);

  const handleAutoImport = async () => {
    if (autoFetchOps.length === 0) return;
    setIsImporting(true);
    setMessage(null);
    try {
      const result = await importTreasuryOperations(clanId, autoFetchOps);
      if (result.success) {
        setImportResult(result);
        setMessage({
          type: 'success',
          text: `Импортировано ${result.imported}, обновлено ${result.updated}, пропущено ${result.skipped}`,
        });
        const data = await getTreasuryOperations(clanId);
        setDbOperations(data);
        setAutoFetchOps([]);
        loadDateCoverage();
        onImportComplete?.();
      } else {
        setMessage({ type: 'error', text: result.message || 'Ошибка при импорте' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: `Ошибка: ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setIsImporting(false);
    }
  };

  const allParsedRows = useMemo((): ParsedRow[] => {
    if (autoFetchOps.length > 0) {
      if (!selectedStartDate && !selectedEndDate) return autoFetchOps;
      return autoFetchOps.filter((row) => {
        const d = parseDate(row.date);
        if (!d) return false;
        const rowComparable = `${d.year}${String(d.month).padStart(2, '0')}${String(d.day).padStart(2, '0')}`;
        if (selectedStartDate) {
          const startD = parseDate(selectedStartDate);
          if (startD) {
            const startComparable = `${startD.year}${String(startD.month).padStart(2, '0')}${String(startD.day).padStart(2, '0')}`;
            if (rowComparable < startComparable) return false;
          }
        }
        if (selectedEndDate) {
          const endD = parseDate(selectedEndDate);
          if (endD) {
            const endComparable = `${endD.year}${String(endD.month).padStart(2, '0')}${String(endD.day).padStart(2, '0')}`;
            if (rowComparable > endComparable) return false;
          }
        }
        return true;
      });
    }
    if (!pastedHtml.trim()) return [];
    return parseTreasuryOperations(pastedHtml);
  }, [pastedHtml, autoFetchOps, selectedStartDate, selectedEndDate]);

  const importStatuses = useMemo((): Map<string, ImportStatus> => {
    const statuses = new Map<string, ImportStatus>();
    if (!allParsedRows.length) return statuses;

    for (const row of allParsedRows) {
      const key = `${row.date}|${row.nick}|${row.operation_type}|${row.object_name}|${row.quantity}`;
      const existing = dbOperations.find(
        (op) =>
          op.date === row.date &&
          op.nick === row.nick &&
          op.operation_type === row.operation_type &&
          op.object_name === row.object_name
      );
      if (existing) {
        statuses.set(key, {
          type: existing.quantity === row.quantity ? 'same' : 'updated',
          existingRecord: existing,
          oldQuantity: existing.quantity,
        });
      } else {
        statuses.set(key, { type: 'new' });
      }
    }
    return statuses;
  }, [allParsedRows, dbOperations]);

  const htmlDateRange = useMemo((): { start: string; end: string; count: number } | null => {
    if (allParsedRows.length === 0) return null;

    const dates = allParsedRows
      .map((r) => parseDate(r.date))
      .filter((d): d is NonNullable<typeof d> => d !== null)
      .map((d) => new Date(d.year, d.month - 1, d.day).getTime());

    if (dates.length === 0) return { start: '?', end: '?', count: allParsedRows.length };

    const minDate = new Date(Math.min(...dates));
    const maxDate = new Date(Math.max(...dates));

    const formatD = (d: Date) => `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`;

    return {
      start: formatD(minDate),
      end: formatD(maxDate),
      count: allParsedRows.length,
    };
  }, [allParsedRows]);

  const previewStats = useMemo(() => {
    let newCount = 0;
    let updatedCount = 0;
    let sameCount = 0;
    for (const status of importStatuses.values()) {
      if (status.type === 'new') newCount++;
      else if (status.type === 'updated') updatedCount++;
      else sameCount++;
    }
    return { newCount, updatedCount, sameCount, total: allParsedRows.length };
  }, [importStatuses, allParsedRows]);

  const significantRows = useMemo(() => {
    return allParsedRows.filter((row) => {
      const key = `${row.date}|${row.nick}|${row.operation_type}|${row.object_name}|${row.quantity}`;
      const status = importStatuses.get(key);
      return status?.type === 'new' || status?.type === 'updated';
    });
  }, [allParsedRows, importStatuses]);

  const handleHtmlImport = async () => {
    if (!pastedHtml.trim()) {
      setMessage({ type: 'error', text: 'Вставьте HTML код страницы' });
      return;
    }

    setIsImporting(true);
    setMessage(null);
    setImportResult(null);

    try {
      const result = await importTreasuryOperations(clanId, parseTreasuryOperations(pastedHtml));
      setImportResult(result);

      if (result.success) {
        setMessage({
          type: 'success',
          text: `Импортировано ${result.imported}, обновлено ${result.updated}, пропущено ${result.skipped}`,
        });
        const data = await getTreasuryOperations(clanId);
        setDbOperations(data);
        setPastedHtml('');
        loadDateCoverage();
        onImportComplete?.();
      } else {
        setMessage({ type: 'error', text: result.message || 'Ошибка при импорте' });
      }
    } catch (err) {
      setMessage({
        type: 'error',
        text: `Ошибка: ${err instanceof Error ? err.message : String(err)}`,
      });
    } finally {
      setIsImporting(false);
    }
  };

  const handleClear = () => {
    setPastedHtml('');
    setAutoFetchOps([]);
    setMessage(null);
    setImportResult(null);
  };

  const formatCookieDate = (iso?: string | null) => {
    if (!iso) return '?';
    const d = new Date(iso);
    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

  return (
    <div className="treasury-import-tab">
      {message && (
        <div className={`treasury-import-message treasury-import-message-${message.type}`}>
          {message.text}
        </div>
      )}

      <section className="treasury-import-section treasury-cookies-section">
            <h3 className="treasury-import-section-title">Авторизация на dwar.ru</h3>
            <div className="treasury-cookies-status">
              {cookieStatus.has_cookies ? (
                <>
                  <span className={`cookie-status-badge ${cookieStatus.is_valid ? 'valid' : 'invalid'}`}>
                    {cookieStatus.is_valid ? 'Cookies активны' : 'Cookies недействительны'}
                  </span>
                  <span className="cookie-status-date">
                    Обновлены: {formatCookieDate(cookieStatus.updated_at)}
                  </span>
                  <Button variant="secondary" size="small" onClick={openCookieEditor}>
                    Обновить cookies
                  </Button>
                </>
              ) : (
                <>
                  <span className="cookie-status-badge none">Cookies не настроены</span>
                  <Button variant="secondary" size="small" onClick={openCookieEditor}>
                    Настроить cookies
                  </Button>
                </>
              )}
            </div>

            {showCookieEditor && (
              <div className="treasury-cookies-editor">
                <div className="treasury-cookies-instructions">
                  <p>Как получить cookies:</p>
                  <ol>
                    <li>Откройте <a href={TREASURY_CLAN_REPORT_URL} target="_blank" rel="noopener noreferrer">Операции казны</a> в браузере</li>
                    <li>F12 → Application/Storage → Cookies → w1.dwar.ru</li>
                    <li>Скопируйте значения нужных cookies в поля ниже</li>
                  </ol>
                  <p className="cookie-note">
                    <strong>Все поля обязательны</strong> — без любого из них авторизация не работает.
                    Остальные cookies (Google Analytics <code>__utm*</code>, Яндекс.Метрика <code>_ym*</code>, <code>cid</code>, <code>flash_version</code>) — не нужны.
                  </p>
                </div>

                <div className="cookie-bulk-toggle">
                  <button
                    type="button"
                    className="cookie-bulk-btn"
                    onClick={() => setShowBulkInput(!showBulkInput)}
                  >
                    {showBulkInput ? 'Показать отдельные поля' : 'Вставить все cookies одной строкой'}
                  </button>
                </div>

                {showBulkInput ? (
                  <div className="cookie-bulk-area">
                    <textarea
                      className="treasury-import-textarea cookie-bulk-textarea"
                      value={bulkCookieInput}
                      onChange={(e) => setBulkCookieInput(e.target.value)}
                      placeholder="sess_sid=...; sess_uid=...; sess_crc=...; mycom=...; ..."
                      rows={4}
                    />
                    <Button variant="secondary" size="small" onClick={handleParseBulkCookies} disabled={!bulkCookieInput.trim()}>
                      Распознать
                    </Button>
                  </div>
                ) : (
                  <div className="cookie-fields-grid">
                    {COOKIE_FIELDS.map((field) => (
                      <CookieField
                        key={field.key}
                        field={field}
                        value={cookieValues[field.key] || ''}
                        onChange={(val) => setCookieValues((prev) => ({ ...prev, [field.key]: val }))}
                        validationStatus={
                          cookieValues[field.key]?.trim()
                            ? 'ok'
                            : field.required
                              ? 'missing'
                              : 'empty'
                        }
                      />
                    ))}
                  </div>
                )}

                <div className="treasury-cookies-actions">
                  <Button variant="secondary" size="small" onClick={() => { setShowCookieEditor(false); setBulkCookieInput(''); }}>
                    Отмена
                  </Button>
                  <Button variant="primary" size="small" onClick={handleSaveCookies} disabled={isSavingCookies}>
                    {isSavingCookies ? 'Проверка...' : 'Сохранить и проверить'}
                  </Button>
                </div>
              </div>
            )}
          </section>

          {cookieStatus.has_cookies && cookieStatus.is_valid && (
            <>
              <section className="treasury-import-section treasury-coverage-section">
                <h3 className="treasury-import-section-title">Покрытие базы данных</h3>
                {dateCoverage && dateCoverage.total_dates_with_data > 0 ? (
                  <>
                    <div className="coverage-summary">
                      <span>{dateCoverage.total_dates_with_data} дней с данными</span>
                      <span>{dateCoverage.total_operations} операций</span>
                      {dateCoverage.earliest_date && dateCoverage.latest_date && (
                        <span>{dateCoverage.earliest_date} — {dateCoverage.latest_date}</span>
                      )}
                    </div>
                    <div className="coverage-tree">
                      {Object.entries(dateCoverage.years).map(([year, yearData]) => {
                        const yearKey = year;
                        const isYearExpanded = expandedYears.has(yearKey);
                        return (
                          <div key={yearKey} className="coverage-year">
                            <button
                              className="coverage-year-header"
                              onClick={() => {
                                const next = new Set(expandedYears);
                                if (next.has(yearKey)) next.delete(yearKey); else next.add(yearKey);
                                setExpandedYears(next);
                              }}
                            >
                              <span className="coverage-toggle">{isYearExpanded ? '▾' : '▸'}</span>
                              <span className="coverage-year-label">{year}</span>
                              <span className="coverage-year-count">{yearData.total_ops} операций</span>
                            </button>
                            {isYearExpanded && (
                              <div className="coverage-months">
                                {Object.entries(yearData.months).map(([month, monthData]) => {
                                  const monthKey = `${yearKey}-${month}`;
                                  const isMonthExpanded = expandedMonths.has(monthKey);
                                  const monthName = MONTHS_RU[parseInt(month, 10)] || month;
                                  return (
                                    <div key={monthKey} className="coverage-month">
                                      <button
                                        className="coverage-month-header"
                                        onClick={() => {
                                          const next = new Set(expandedMonths);
                                          if (next.has(monthKey)) next.delete(monthKey); else next.add(monthKey);
                                          setExpandedMonths(next);
                                        }}
                                      >
                                        <span className="coverage-toggle">{isMonthExpanded ? '▾' : '▸'}</span>
                                        <span>{monthName}</span>
                                        <span className="coverage-month-count">{monthData.total_ops} операций</span>
                                      </button>
                                      {isMonthExpanded && (
                                        <div className="coverage-days">
                                           {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => {
                                             const dayStr = day.toString().padStart(2, '0');
                                             const hasData = monthData.days.includes(dayStr);
                                             const dateKey = `${dayStr}.${month}.${year}`;
                                             const isSelectedStart = selectedStartDate === dateKey;
                                             const isSelectedEnd = selectedEndDate === dateKey;
                                             return (
                                               <div
                                                 key={day}
                                                 className={`coverage-day ${hasData ? 'has-data' : ''} ${isSelectedStart ? 'selected-start' : ''} ${isSelectedEnd ? 'selected-end' : ''}`}
                                                 onClick={() => hasData && setSelectedStartDate(dateKey)}
                                                 onContextMenu={(e) => {
                                                   e.preventDefault();
                                                   if (hasData) setSelectedEndDate(dateKey);
                                                 }}
                                               >
                                                 {day}
                                               </div>
                                             );
                                          })}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                     </div>
                     {(selectedStartDate || selectedEndDate) && (
                       <div className="coverage-selected">
                         Диапазон импорта: <strong>{selectedStartDate || 'начало'}</strong> — <strong>{selectedEndDate || 'текущая дата'}</strong>
                         <span className="coverage-hint">(ЛКМ — дата старта, ПКМ — дата окончания)</span>
                       </div>
                     )}
                  </>
                ) : (
                  <div className="coverage-empty">
                    <p>Нет данных в базе. Запустите первый импорт.</p>
                    <Button variant="secondary" size="small" onClick={loadDateCoverage}>
                      Обновить
                    </Button>
                  </div>
                )}
              </section>

                <section className="treasury-import-section treasury-auto-fetch-section">
                  <h3 className="treasury-import-section-title">Сбор данных</h3>
                  <div className="treasury-auto-fetch-info">
                    <p>Данные будут собраны за период: <strong>{selectedStartDate || '01.01.2025'}</strong> — <strong>{selectedEndDate || 'текущая дата'}</strong>.</p>
                  </div>
                  {autoFetchOps.length === 0 && !isAutoFetching && fetchProgress.phase !== 'error' && (
                    <>
                      {!pageEstimate && !isEstimating && (
                        <Button variant="primary" onClick={estimatePages}>
                          Оценить количество страниц
                        </Button>
                      )}
                      {isEstimating && (
                        <div className="treasury-auto-fetch-progress">
                          <div className="progress-bar-container">
                            <div className="progress-bar">
                              <div className="progress-bar-fill" style={{ width: '100%', animation: 'pulse 1.5s ease-in-out infinite' }} />
                            </div>
                          </div>
                          <div className="progress-details">
                            <span className="progress-text">Оценка количества страниц...</span>
                          </div>
                        </div>
                      )}
                      {pageEstimate && !isEstimating && (
                        <div className="treasury-estimate-result">
                          <p className="estimate-summary">
                            Найдено <strong>~{pageEstimate.estimated_pages} страниц</strong> из {pageEstimate.total_pages} в выбранном диапазоне.
                          </p>
                          <div className="estimate-details">
                            <span>Страницы: {pageEstimate.start_page} → {pageEstimate.end_page}</span>
                          </div>
                          <Button variant="primary" onClick={() => {
                            const est = pageEstimateRef.current;
                            if (!est) { estimatePages(); return; }
                            setIsAutoFetching(true);
                            setMessage(null);
                            setAutoFetchOps([]);
                            setFetchProgress({ phase: 'counting', totalPages: est.total_pages, currentPage: 0, totalOps: 0, opsOnPage: 0, elapsed: 0, message: `Начинаю сбор: ~${est.estimated_pages} страниц...` });
                            const apiBase = import.meta.env.VITE_API_URL || window.location.origin;
                            const token = localStorage.getItem('auth_token');
                            const startDate = selectedStartDate || '01.01.2025';
                            const params = new URLSearchParams({ token: token || '' });
                            if (startDate !== '01.01.2025') params.set('start_date', startDate);
                            if (selectedEndDate) params.set('end_date', selectedEndDate);
                            params.set('start_page', String(est.start_page));
                            params.set('end_page', String(est.end_page + 1));
                            params.set('total_pages', String(est.total_pages));
                            const url = `${apiBase}/api/clan/${clanId}/treasury/auto-fetch-stream?${params.toString()}`;
                            const es = new EventSource(url);
                            es.onmessage = (e) => {
                              try {
                                const data = JSON.parse(e.data);
                                switch (data.type) {
                                  case 'counting':
                                    setFetchProgress({ phase: 'fetching', totalPages: data.total_pages, currentPage: 0, totalOps: 0, opsOnPage: 0, elapsed: 0, message: `Найдено ${data.total_pages} страниц. Начинаю сбор...` });
                                    break;
                                  case 'progress':
                                    const pct = data.total_pages > 0 ? Math.round(((data.page + 1) / data.total_pages) * 100) : 0;
                                    const elapsed = data.elapsed || 0;
                                    const opsPerSec = data.page > 0 ? data.total_ops / elapsed : 0;
                                    const remaining = data.total_pages - data.page - 1;
                                    const eta = opsPerSec > 0 && remaining > 0 ? Math.round(remaining / opsPerSec) : 0;
                                    setFetchProgress({ phase: 'fetching', totalPages: data.total_pages, currentPage: data.page + 1, totalOps: data.total_ops, opsOnPage: data.ops_on_page, elapsed, message: `Страница ${data.page + 1} из ${data.total_pages} (${pct}%) · ${data.total_ops} операций${eta > 0 ? ` · ~${eta}с осталось` : ''}` });
                                    break;
                                  case 'done':
                                    setAutoFetchOps(data.operations as ParsedRow[]);
                                    setFetchProgress({ phase: 'done', totalPages: data.pages_fetched, currentPage: data.pages_fetched, totalOps: data.total_ops, opsOnPage: 0, elapsed: data.elapsed, message: `Собрано ${data.total_ops} операций со ${data.pages_fetched} страниц за ${data.elapsed}с` });
                                    es.close();
                                    setEventSource(null);
                                    setIsAutoFetching(false);
                                    break;
                                  case 'error':
                                    setFetchProgress({ phase: 'error', totalPages: 0, currentPage: 0, totalOps: 0, opsOnPage: 0, elapsed: 0, message: data.message || 'Ошибка при сборе данных' });
                                    if (data.reason === 'session_expired') refreshCookieStatus();
                                    es.close();
                                    setEventSource(null);
                                    setIsAutoFetching(false);
                                    break;
                                }
                              } catch (err) { console.error('SSE parse error:', err); }
                            };
                            es.onerror = () => {
                              setFetchProgress((prev) => ({ ...prev, phase: 'error', message: prev.phase === 'error' ? prev.message : 'Соединение потеряно' }));
                              es.close();
                              setEventSource(null);
                              setIsAutoFetching(false);
                            };
                            setEventSource(es);
                          }}>
                            Начать сбор ({pageEstimate.estimated_pages} страниц)
                          </Button>
                          <Button variant="secondary" size="small" onClick={() => setPageEstimate(null)} style={{ marginLeft: '8px' }}>
                            Пересчитать
                          </Button>
                        </div>
                      )}
                    </>
                  )}
              {isAutoFetching && (
                <div className="treasury-auto-fetch-progress">
                  <div className="progress-bar-container">
                    <div className="progress-bar">
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${fetchProgress.totalPages > 0 ? (fetchProgress.currentPage / fetchProgress.totalPages) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="progress-percentage">
                      {fetchProgress.totalPages > 0 ? Math.round((fetchProgress.currentPage / fetchProgress.totalPages) * 100) : 0}%
                    </span>
                  </div>
                  <div className="progress-details">
                    <span className="progress-text">{fetchProgress.message}</span>
                    <div className="progress-stats">
                      <span className="stat-item">
                        <span className="stat-label">Страницы:</span>
                        <span className="stat-value">{fetchProgress.currentPage} / {fetchProgress.totalPages}</span>
                      </span>
                      <span className="stat-item">
                        <span className="stat-label">Операции:</span>
                        <span className="stat-value">{fetchProgress.totalOps}</span>
                      </span>
                      <span className="stat-item">
                        <span className="stat-label">Время:</span>
                        <span className="stat-value">{fetchProgress.elapsed}с</span>
                      </span>
                    </div>
                  </div>
                  <Button variant="danger" size="small" onClick={cancelAutoFetch}>
                    Отменить
                  </Button>
                </div>
              )}
              {!isAutoFetching && fetchProgress.phase === 'error' && fetchProgress.message && (
                <div className="treasury-auto-fetch-error">
                  <p>{fetchProgress.message}</p>
                  {fetchProgress.totalPages === 0 && (
                    <Button variant="secondary" size="small" onClick={handleAutoFetch}>
                      Попробовать снова
                    </Button>
                  )}
                </div>
              )}
              {autoFetchOps.length > 0 && !isAutoFetching && (
                <div className="treasury-auto-fetch-result">
                  <p className="auto-fetch-summary">
                    Сбор завершён. Найдено <strong>{autoFetchOps.length}</strong> операций.
                    {htmlDateRange && (
                      <> Период: {htmlDateRange.start} — {htmlDateRange.end}.</>
                    )}
                  </p>
                  <p className="auto-fetch-hint">
                    Просмотрите изменения в таблице ниже и нажмите «Импортировать» для записи в БД.
                  </p>
                </div>
              )}
            </section>
            </>
          )}

      {(allParsedRows.length > 0 || pastedHtml.trim()) && (
        <>
          <div className="treasury-import-summary-row">
            <section className="treasury-import-section treasury-import-summary">
              {htmlDateRange ? (
                <>
                  <div className="treasury-import-date-range">
                    <span className="date-range-label">Операции за период:</span>
                    <span className="date-range-value">
                      {htmlDateRange.start} — {htmlDateRange.end}
                    </span>
                    <span className="date-range-count">({htmlDateRange.count} записей)</span>
                  </div>
                  <div className="treasury-import-preview-stats">
                    <span className="preview-stat preview-stat-new">
                      <span className="preview-stat-indicator">+</span> новых: <strong>{previewStats.newCount}</strong>
                    </span>
                    <span className="preview-stat preview-stat-updated">
                      <span className="preview-stat-indicator">~</span> обновится: <strong>{previewStats.updatedCount}</strong>
                    </span>
                    <span className="preview-stat preview-stat-same">
                      <span className="preview-stat-indicator">=</span> без изменений: <strong>{previewStats.sameCount}</strong>
                    </span>
                  </div>
                </>
              ) : (
                <div className="treasury-import-placeholder">
                  {pastedHtml.trim() && allParsedRows.length === 0
                    ? 'Не удалось распознать операции. Проверьте формат HTML.'
                    : 'Нет новых операций для импорта'}
                </div>
              )}
            </section>
            <div className="treasury-import-summary-actions">
              <Button variant="secondary" onClick={handleClear}>
                Сбросить
              </Button>
              {(allParsedRows.length > 0 || pastedHtml.trim()) && (
                <Button variant="primary" onClick={autoFetchOps.length > 0 ? handleAutoImport : handleHtmlImport} disabled={isImporting}>
                  {isImporting ? 'Запись в БД...' : `Импортировать ${allParsedRows.length > 0 ? allParsedRows.length : 'HTML'}`}
                </Button>
              )}
            </div>
          </div>

          {isImporting && (
            <div className="treasury-import-progress-bar">
              <div className="import-progress-container">
                <div className="import-progress-fill" />
              </div>
              <span className="import-progress-text">Запись операций в базу данных...</span>
            </div>
          )}

          <section className="treasury-import-section treasury-import-preview">
            <h3 className="treasury-import-section-title">
              {significantRows.length > 0 ? `Изменения (${significantRows.length})` : 'Изменения'}
            </h3>
            {significantRows.length > 0 ? (
              <div className="treasury-import-table-container">
                <table className="treasury-import-table">
                  <thead>
                    <tr>
                      <th>Статус</th>
                      <th>Дата</th>
                      <th>Игрок</th>
                      <th>Тип</th>
                      <th>Объект</th>
                      <th>Значение</th>
                    </tr>
                  </thead>
                  <tbody>
                    {significantRows.map((row, index) => {
                      const key = `${row.date}|${row.nick}|${row.operation_type}|${row.object_name}|${row.quantity}`;
                      const status = importStatuses.get(key);
                      const isUpdated = status?.type === 'updated';
                      return (
                        <tr key={index} className={isUpdated ? 'row-updated' : 'row-new'}>
                          <td>
                            <span className={`preview-status preview-status-${status?.type}`}>
                              {status?.type === 'new' && '+'}
                              {status?.type === 'updated' && '~'}
                            </span>
                          </td>
                          <td>{row.date}</td>
                          <td>{row.nick}</td>
                          <td>{row.operation_type}</td>
                          <td>{row.object_name}</td>
                          <td className="quantity-cell">
                            {isUpdated && (
                              <span className="quantity-old">{status.oldQuantity}</span>
                            )}
                            <span className={`quantity-new ${row.quantity >= 0 ? 'positive' : 'negative'}`}>
                              {row.quantity >= 0 ? '+' : ''}
                              {row.quantity}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              allParsedRows.length > 0 ? (
                <div className="treasury-import-all-same">
                  <p>Все {allParsedRows.length} операций уже существуют без изменений</p>
                </div>
              ) : (
                <div className="treasury-import-placeholder">
                  Предпросмотр изменений появится здесь
                </div>
              )
            )}
          </section>

          {importResult && (
            <section className="treasury-import-section treasury-import-result">
              <h3 className="treasury-import-section-title">Результат импорта</h3>
              <div className="treasury-import-result-grid">
                <div className="treasury-import-result-item">
                  <span className="treasury-import-result-label">Создано новых:</span>
                  <span className="treasury-import-result-value success">{importResult.imported}</span>
                </div>
                <div className="treasury-import-result-item">
                  <span className="treasury-import-result-label">Обновлено:</span>
                  <span className="treasury-import-result-value">{importResult.updated}</span>
                </div>
                <div className="treasury-import-result-item">
                  <span className="treasury-import-result-label">Пропущено:</span>
                  <span className="treasury-import-result-value">{importResult.skipped}</span>
                </div>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function HtmlImportTab({ clanId, onImportComplete }: { clanId: number; onImportComplete?: () => void }) {
  const [pastedHtml, setPastedHtml] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [importResult, setImportResult] = useState<{ imported: number; updated: number; skipped: number } | null>(null);
  const [dbOperations, setDbOperations] = useState<TreasuryOperationData[]>([]);

  useEffect(() => {
    getTreasuryOperations(clanId).then(setDbOperations).catch(() => setDbOperations([]));
  }, [clanId]);

  const parsedRows = useMemo((): ParsedRow[] => {
    if (!pastedHtml.trim()) return [];
    return parseTreasuryOperations(pastedHtml);
  }, [pastedHtml]);

  const importStatuses = useMemo((): Map<string, ImportStatus> => {
    const statuses = new Map<string, ImportStatus>();
    if (!parsedRows.length) return statuses;
    for (const row of parsedRows) {
      const key = `${row.date}|${row.nick}|${row.operation_type}|${row.object_name}|${row.quantity}`;
      const existing = dbOperations.find(
        (op) =>
          op.date === row.date &&
          op.nick === row.nick &&
          op.operation_type === row.operation_type &&
          op.object_name === row.object_name
      );
      if (existing) {
        statuses.set(key, {
          type: existing.quantity === row.quantity ? 'same' : 'updated',
          existingRecord: existing,
          oldQuantity: existing.quantity,
        });
      } else {
        statuses.set(key, { type: 'new' });
      }
    }
    return statuses;
  }, [parsedRows, dbOperations]);

  const htmlDateRange = useMemo((): { start: string; end: string; count: number } | null => {
    if (parsedRows.length === 0) return null;
    const dates = parsedRows
      .map((r) => parseDate(r.date))
      .filter((d): d is NonNullable<typeof d> => d !== null)
      .map((d) => new Date(d.year, d.month - 1, d.day).getTime());
    if (dates.length === 0) return { start: '?', end: '?', count: parsedRows.length };
    const minDate = new Date(Math.min(...dates));
    const maxDate = new Date(Math.max(...dates));
    const formatD = (d: Date) => `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`;
    return { start: formatD(minDate), end: formatD(maxDate), count: parsedRows.length };
  }, [parsedRows]);

  const previewStats = useMemo(() => {
    let newCount = 0;
    let updatedCount = 0;
    let sameCount = 0;
    for (const status of importStatuses.values()) {
      if (status.type === 'new') newCount++;
      else if (status.type === 'updated') updatedCount++;
      else sameCount++;
    }
    return { newCount, updatedCount, sameCount, total: parsedRows.length };
  }, [importStatuses, parsedRows]);

  const significantRows = useMemo(() => {
    return parsedRows.filter((row) => {
      const key = `${row.date}|${row.nick}|${row.operation_type}|${row.object_name}|${row.quantity}`;
      const status = importStatuses.get(key);
      return status?.type === 'new' || status?.type === 'updated';
    });
  }, [parsedRows, importStatuses]);

  const handleImport = async () => {
    if (!pastedHtml.trim()) {
      setMessage({ type: 'error', text: 'Вставьте HTML код страницы' });
      return;
    }
    setIsImporting(true);
    setMessage(null);
    setImportResult(null);
    try {
      const result = await importTreasuryOperations(clanId, parseTreasuryOperations(pastedHtml));
      setImportResult(result);
      if (result.success) {
        setMessage({
          type: 'success',
          text: `Импортировано ${result.imported}, обновлено ${result.updated}, пропущено ${result.skipped}`,
        });
        const data = await getTreasuryOperations(clanId);
        setDbOperations(data);
        setPastedHtml('');
        onImportComplete?.();
      } else {
        setMessage({ type: 'error', text: result.message || 'Ошибка при импорте' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: `Ошибка: ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setIsImporting(false);
    }
  };

  const handleClear = () => {
    setPastedHtml('');
    setMessage(null);
    setImportResult(null);
  };

  return (
    <div className="treasury-import-tab">
      {message && (
        <div className={`treasury-import-message treasury-import-message-${message.type}`}>
          {message.text}
        </div>
      )}

      <section className="treasury-import-section">
        <h3 className="treasury-import-section-title">HTML данные</h3>
        <div className="treasury-import-instructions">
          <ol>
            <li>
              Откройте{' '}
              <a href={TREASURY_CLAN_REPORT_URL} target="_blank" rel="noopener noreferrer">
                Операции казны
              </a>{' '}
              в браузере
            </li>
            <li>Нажмите Ctrl+U для просмотра кода страницы</li>
            <li>Ctrl+A → Ctrl+C для копирования всего кода</li>
            <li>Вставьте в поле ниже (Ctrl+V)</li>
          </ol>
        </div>
        <textarea
          className="treasury-import-textarea"
          value={pastedHtml}
          onChange={(e) => setPastedHtml(e.target.value)}
          placeholder="Вставьте HTML код страницы..."
          rows={12}
        />
      </section>

      {parsedRows.length > 0 && (
        <>
          <div className="treasury-import-summary-row">
            <section className="treasury-import-section treasury-import-summary">
              {htmlDateRange ? (
                <>
                  <div className="treasury-import-date-range">
                    <span className="date-range-label">Операции за период:</span>
                    <span className="date-range-value">
                      {htmlDateRange.start} — {htmlDateRange.end}
                    </span>
                    <span className="date-range-count">({htmlDateRange.count} записей)</span>
                  </div>
                  <div className="treasury-import-preview-stats">
                    <span className="preview-stat preview-stat-new">
                      <span className="preview-stat-indicator">+</span> новых: <strong>{previewStats.newCount}</strong>
                    </span>
                    <span className="preview-stat preview-stat-updated">
                      <span className="preview-stat-indicator">~</span> обновится: <strong>{previewStats.updatedCount}</strong>
                    </span>
                    <span className="preview-stat preview-stat-same">
                      <span className="preview-stat-indicator">=</span> без изменений: <strong>{previewStats.sameCount}</strong>
                    </span>
                  </div>
                </>
              ) : (
                <div className="treasury-import-placeholder">Нет новых операций для импорта</div>
              )}
            </section>
            <div className="treasury-import-summary-actions">
              <Button variant="secondary" onClick={handleClear}>Сбросить</Button>
              <Button variant="primary" onClick={handleImport} disabled={isImporting}>
                {isImporting ? 'Запись в БД...' : `Импортировать ${parsedRows.length}`}
              </Button>
            </div>
          </div>

          {isImporting && (
            <div className="treasury-import-progress-bar">
              <div className="import-progress-container">
                <div className="import-progress-fill" />
              </div>
              <span className="import-progress-text">Запись операций в базу данных...</span>
            </div>
          )}

          <section className="treasury-import-section treasury-import-preview">
            <h3 className="treasury-import-section-title">
              {significantRows.length > 0 ? `Изменения (${significantRows.length})` : 'Изменения'}
            </h3>
            {significantRows.length > 0 ? (
              <div className="treasury-import-table-container">
                <table className="treasury-import-table">
                  <thead>
                    <tr>
                      <th>Статус</th>
                      <th>Дата</th>
                      <th>Игрок</th>
                      <th>Тип</th>
                      <th>Объект</th>
                      <th>Значение</th>
                    </tr>
                  </thead>
                  <tbody>
                    {significantRows.map((row, index) => {
                      const key = `${row.date}|${row.nick}|${row.operation_type}|${row.object_name}|${row.quantity}`;
                      const status = importStatuses.get(key);
                      const isUpdated = status?.type === 'updated';
                      return (
                        <tr key={index} className={isUpdated ? 'row-updated' : 'row-new'}>
                          <td>
                            <span className={`preview-status preview-status-${status?.type}`}>
                              {status?.type === 'new' && '+'}
                              {status?.type === 'updated' && '~'}
                            </span>
                          </td>
                          <td>{row.date}</td>
                          <td>{row.nick}</td>
                          <td>{row.operation_type}</td>
                          <td>{row.object_name}</td>
                          <td className="quantity-cell">
                            {isUpdated && (
                              <span className="quantity-old">{status.oldQuantity}</span>
                            )}
                            <span className={`quantity-new ${row.quantity >= 0 ? 'positive' : 'negative'}`}>
                              {row.quantity >= 0 ? '+' : ''}
                              {row.quantity}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              parsedRows.length > 0 ? (
                <div className="treasury-import-all-same">
                  <p>Все {parsedRows.length} операций уже существуют без изменений</p>
                </div>
              ) : (
                <div className="treasury-import-placeholder">Предпросмотр изменений появится здесь</div>
              )
            )}
          </section>

          {importResult && (
            <section className="treasury-import-section treasury-import-result">
              <h3 className="treasury-import-section-title">Результат импорта</h3>
              <div className="treasury-import-result-grid">
                <div className="treasury-import-result-item">
                  <span className="treasury-import-result-label">Создано новых:</span>
                  <span className="treasury-import-result-value success">{importResult.imported}</span>
                </div>
                <div className="treasury-import-result-item">
                  <span className="treasury-import-result-label">Обновлено:</span>
                  <span className="treasury-import-result-value">{importResult.updated}</span>
                </div>
                <div className="treasury-import-result-item">
                  <span className="treasury-import-result-label">Пропущено:</span>
                  <span className="treasury-import-result-value">{importResult.skipped}</span>
                </div>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function ExportTab({ clanId }: { clanId: number }) {
  const [showBackupPicker, setShowBackupPicker] = useState(false);
  const [backupPickerMode, setBackupPickerMode] = useState<'save' | 'restore'>('save');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleShowBackupPicker = (mode: 'save' | 'restore') => {
    setBackupPickerMode(mode);
    setShowBackupPicker(true);
  };

  const handleBackupSuccess = (msg: string) => {
    setMessage({ type: 'success', text: msg });
  };

  return (
    <div className="treasury-export-tab">
      {message && (
        <div className={`treasury-import-message treasury-import-message-${message.type}`}>
          {message.text}
        </div>
      )}

      <section className="treasury-import-section">
        <h3 className="treasury-import-section-title">Экспорт данных</h3>
        <div className="treasury-export-description">
          <p>
            <strong>Экспорт</strong> создаёт резервную копию всех операций казны текущего клана.
            Файл сохраняется на сервере и содержит полную историю операций.
          </p>
          <p>
            Используйте экспорт для создания резервной копии перед массовым импортом данных или для
            сохранения истории за определённый период.
          </p>
        </div>
        <div className="treasury-export-actions">
          <Button variant="primary" onClick={() => handleShowBackupPicker('save')}>
            Создать резервную копию
          </Button>
        </div>
      </section>

      <section className="treasury-import-section">
        <h3 className="treasury-import-section-title">Восстановление данных</h3>
        <div className="treasury-export-description">
          <p>
            <strong>Восстановление</strong> позволяет загрузить данные из ранее созданной
            резервной копии. Это полностью заменит текущие данные казны.
          </p>
          <p className="treasury-export-warning">
            ⚠️ Восстановление перезаписывает текущие данные! Убедитесь, что у вас есть
            актуальная резервная копия перед восстановлением.
          </p>
        </div>
        <div className="treasury-export-actions">
          <Button variant="secondary" onClick={() => handleShowBackupPicker('restore')}>
            Восстановить из резервной копии
          </Button>
        </div>
      </section>

      <BackupPicker
        isOpen={showBackupPicker}
        onClose={() => setShowBackupPicker(false)}
        clanId={clanId}
        mode={backupPickerMode}
        onSuccess={handleBackupSuccess}
      />
    </div>
  );
}
function CookiesTab({ clanId }: { clanId: number }) {
  const [cookieStatus, setCookieStatus] = useState<{ has_cookies: boolean; is_valid: boolean; updated_at?: string | null }>({ has_cookies: false, is_valid: false });
  const [showCookieEditor, setShowCookieEditor] = useState(false);
  const [cookieValues, setCookieValues] = useState<Record<string, string>>({});
  const [isSavingCookies, setIsSavingCookies] = useState(false);
  const [bulkCookieInput, setBulkCookieInput] = useState('');
  const [showBulkInput, setShowBulkInput] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    getTreasuryCookiesStatus(clanId).then(setCookieStatus).catch(() => setCookieStatus({ has_cookies: false, is_valid: false }));
  }, [clanId]);

  const refreshCookieStatus = useCallback(() => {
    getTreasuryCookiesStatus(clanId).then(setCookieStatus).catch(() => setCookieStatus({ has_cookies: false, is_valid: false }));
  }, [clanId]);

  const openCookieEditor = () => {
    setShowCookieEditor(true);
    setShowBulkInput(false);
    setCookieValues({});
    setBulkCookieInput('');
  };

  const handleParseBulkCookies = () => {
    const parsed: Record<string, string> = {};
    for (const field of COOKIE_FIELDS) {
      parsed[field.key] = parseCookieValue(bulkCookieInput, field.key);
    }
    setCookieValues(parsed);
    setShowBulkInput(false);
  };

  const handleSaveCookies = async () => {
    const cookieString = buildCookieString(cookieValues);
    if (!cookieString.trim()) {
      setMessage({ type: 'error', text: 'Заполните все поля cookies' });
      return;
    }

    const missingRequired = COOKIE_FIELDS.filter((f) => f.required && !cookieValues[f.key]?.trim());
    if (missingRequired.length > 0) {
      setMessage({ type: 'error', text: `Не заполнены поля: ${missingRequired.map((f) => f.key).join(', ')}` });
      return;
    }

    setIsSavingCookies(true);
    setMessage(null);
    try {
      const result = await saveTreasuryCookies(clanId, cookieString);
      if (result.success) {
        setMessage({ type: 'success', text: result.message });
        setShowCookieEditor(false);
        setCookieValues({});
        setBulkCookieInput('');
        refreshCookieStatus();
      } else {
        setMessage({ type: 'error', text: result.message || result.error || 'Ошибка сохранения cookies' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: `Ошибка: ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setIsSavingCookies(false);
    }
  };

  const formatCookieDate = (iso?: string | null) => {
    if (!iso) return '?';
    const d = new Date(iso);
    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

  return (
    <div className="treasury-import-tab">
      {message && (
        <div className={`treasury-import-message treasury-import-message-${message.type}`}>
          {message.text}
        </div>
      )}

      <section className="treasury-import-section treasury-cookies-section">
        <h3 className="treasury-import-section-title">Авторизация на dwar.ru</h3>
        <div className="treasury-cookies-status">
          {cookieStatus.has_cookies ? (
            <>
              <span className={`cookie-status-badge ${cookieStatus.is_valid ? 'valid' : 'invalid'}`}>
                {cookieStatus.is_valid ? 'Cookies активны' : 'Cookies недействительны'}
              </span>
              <span className="cookie-status-date">
                Обновлены: {formatCookieDate(cookieStatus.updated_at)}
              </span>
              <Button variant="secondary" size="small" onClick={openCookieEditor}>
                Обновить cookies
              </Button>
            </>
          ) : (
            <>
              <span className="cookie-status-badge none">Cookies не настроены</span>
              <Button variant="secondary" size="small" onClick={openCookieEditor}>
                Настроить cookies
              </Button>
            </>
          )}
        </div>

        {showCookieEditor && (
          <div className="treasury-cookies-editor">
            <div className="treasury-cookies-instructions">
              <p>Как получить cookies:</p>
              <ol>
                <li>Откройте <a href={TREASURY_CLAN_REPORT_URL} target="_blank" rel="noopener noreferrer">Операции казны</a> в браузере</li>
                <li>F12 → Application/Storage → Cookies → w1.dwar.ru</li>
                <li>Скопируйте значения нужных cookies в поля ниже</li>
              </ol>
              <p className="cookie-note">
                <strong>Все поля обязательны</strong> — без любого из них авторизация не работает.
                Остальные cookies (Google Analytics <code>__utm*</code>, Яндекс.Метрика <code>_ym*</code>, <code>cid</code>, <code>flash_version</code>) — не нужны.
              </p>
            </div>

            <div className="cookie-bulk-toggle">
              <button
                type="button"
                className="cookie-bulk-btn"
                onClick={() => setShowBulkInput(!showBulkInput)}
              >
                {showBulkInput ? 'Показать отдельные поля' : 'Вставить все cookies одной строкой'}
              </button>
            </div>

            {showBulkInput ? (
              <div className="cookie-bulk-area">
                <textarea
                  className="treasury-import-textarea cookie-bulk-textarea"
                  value={bulkCookieInput}
                  onChange={(e) => setBulkCookieInput(e.target.value)}
                  placeholder="sess_sid=...; sess_uid=...; sess_crc=...; mycom=...; ..."
                  rows={4}
                />
                <Button variant="secondary" size="small" onClick={handleParseBulkCookies} disabled={!bulkCookieInput.trim()}>
                  Распознать
                </Button>
              </div>
            ) : (
              <div className="cookie-fields-grid">
                {COOKIE_FIELDS.map((field) => (
                  <CookieField
                    key={field.key}
                    field={field}
                    value={cookieValues[field.key] || ''}
                    onChange={(val) => setCookieValues((prev) => ({ ...prev, [field.key]: val }))}
                    validationStatus={
                      cookieValues[field.key]?.trim()
                        ? 'ok'
                        : field.required
                          ? 'missing'
                          : 'empty'
                    }
                  />
                ))}
              </div>
            )}

            <div className="treasury-cookies-actions">
              <Button variant="secondary" size="small" onClick={() => { setShowCookieEditor(false); setBulkCookieInput(''); }}>
                Отмена
              </Button>
              <Button variant="primary" size="small" onClick={handleSaveCookies} disabled={isSavingCookies}>
                {isSavingCookies ? 'Проверка...' : 'Сохранить и проверить'}
              </Button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
