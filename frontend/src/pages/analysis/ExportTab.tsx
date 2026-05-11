import { useState, useCallback } from 'react';
import { exportCharacter, EXPORT_SECTIONS, EXPORT_FORMATS } from '../../api/export';
import type { AnalysisResult } from '../../types/character';
import './ExportTab.css';

interface ExportTabProps {
  currentResult: AnalysisResult | null;
}

export function ExportTab({ currentResult }: ExportTabProps) {
  const [format, setFormat] = useState<'html' | 'markdown' | 'pdf'>('html');
  const [sections, setSections] = useState<Set<string>>(
    new Set(['identity', 'combat_stats', 'characteristics', 'equipment', 'effects', 'medals', 'records', 'professions'])
  );
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  const toggleSection = useCallback((key: string) => {
    setSections(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSections(new Set(EXPORT_SECTIONS.map(s => s.key)));
  }, []);

  const deselectAll = useCallback(() => {
    setSections(new Set());
  }, []);

  const handleExport = async () => {
    if (!currentResult) {
      setError('Сначала проанализируйте персонажа');
      return;
    }
    if (sections.size === 0) {
      setError('Выберите хотя бы один раздел');
      return;
    }

    setExporting(true);
    setError('');

    try {
      const blob = await exportCharacter({
        format,
        sections: Array.from(sections),
        data: currentResult as unknown as Record<string, unknown>,
      });

      // Trigger download
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentResult.name || 'character'}_export.${format === 'markdown' ? 'md' : format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export error:', err);
      setError('Ошибка при экспорте. Попробуйте ещё раз.');
    } finally {
      setExporting(false);
    }
  };

  if (!currentResult) {
    return (
      <div className="export-tab">
        <div className="export-empty">
          <span className="export-empty-icon">📤</span>
          <p>Сначала проанализируйте персонажа, затем экспортируйте отчёт</p>
        </div>
      </div>
    );
  }

  return (
    <div className="export-tab">
      <h2 className="export-title">Экспорт аналитики</h2>

      <div className="export-section">
        <h3>Формат</h3>
        <div className="export-format-group">
          {EXPORT_FORMATS.map(f => (
            <button
              key={f.key}
              className={`export-format-btn ${format === f.key ? 'active' : ''}`}
              onClick={() => setFormat(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="export-section">
        <div className="export-section-header">
          <h3>Разделы для экспорта</h3>
          <div className="export-section-actions">
            <button className="export-link-btn" onClick={selectAll}>Выбрать все</button>
            <button className="export-link-btn" onClick={deselectAll}>Снять все</button>
          </div>
        </div>
        <div className="export-checkboxes">
          {EXPORT_SECTIONS.map(s => (
            <label key={s.key} className="export-checkbox">
              <input
                type="checkbox"
                checked={sections.has(s.key)}
                onChange={() => toggleSection(s.key)}
              />
              <span>{s.label}</span>
            </label>
          ))}
        </div>
      </div>

      {error && <div className="export-error">{error}</div>}

      <button
        className="export-btn"
        onClick={handleExport}
        disabled={exporting || sections.size === 0}
      >
        {exporting ? 'Генерация...' : `Скачать ${format.toUpperCase()}`}
      </button>
    </div>
  );
}
