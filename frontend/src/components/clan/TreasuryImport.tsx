import { useState, useMemo, useEffect } from 'react';
import { getTreasuryOperations, importTreasuryOperations } from '../../api/clanInfo';
import type { TreasuryOperationData } from '../../types/clanInfo';
import { Button } from '../ui/Button';
import { BackupPicker } from './BackupPicker';
import { parseTreasuryOperations, parseDate, TREASURY_CLAN_REPORT_URL } from '../../utils/treasury';
import './TreasuryImport.css';

interface TreasuryImportProps {
  clanId: number;
  onImportComplete?: () => void;
}

type SubTab = 'import' | 'export';

interface ParsedRow {
  date: string;
  nick: string;
  operation_type: string;
  object_name: string;
  quantity: number;
}

interface ImportStatus {
  type: 'new' | 'updated' | 'same';
  existingRecord?: TreasuryOperationData;
  oldQuantity?: number;
}

function ImportTab({ clanId, onImportComplete }: { clanId: number; onImportComplete?: () => void }) {
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

    return {
      start: formatD(minDate),
      end: formatD(maxDate),
      count: parsedRows.length,
    };
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
      const result = await importTreasuryOperations(clanId, parsedRows);
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
          rows={8}
        />
      </section>

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
              Вставьте HTML код для предпросмотра операций
            </div>
          )}
        </section>
        <div className="treasury-import-summary-actions">
          <Button variant="secondary" onClick={handleClear}>
            Очистить
          </Button>
          <Button variant="primary" onClick={handleImport} disabled={isImporting || parsedRows.length === 0}>
            {isImporting ? 'Импорт...' : parsedRows.length > 0 ? `Импортировать ${parsedRows.length}` : 'Импортировать'}
          </Button>
        </div>
      </div>

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

export function TreasuryImport({ clanId, onImportComplete }: TreasuryImportProps) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('import');

  return (
    <div className="treasury-import-page">
      <header className="treasury-import-header">
        <h2 className="treasury-import-title">Импорт / Экспорт</h2>
      </header>

      <div className="treasury-import-tabs">
        <button
          className={`treasury-import-tab-btn ${activeSubTab === 'import' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('import')}
        >
          Импорт
        </button>
        <button
          className={`treasury-import-tab-btn ${activeSubTab === 'export' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('export')}
        >
          Экспорт
        </button>
      </div>

      {activeSubTab === 'import' && <ImportTab clanId={clanId} onImportComplete={onImportComplete} />}
      {activeSubTab === 'export' && <ExportTab clanId={clanId} />}
    </div>
  );
}
