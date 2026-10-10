import { useCallback, useEffect, useState } from 'react';
import { getTreasurySummary } from '../../api/clanInfo';
import type { TreasurySummaryResponse } from '../../types/clanInfo';
import { copyText } from '../../utils/clipboard';
import './TreasurySummaryPanel.css';

interface TreasurySummaryPanelProps {
  clanId?: number;
  /** The month the tab is showing — the summary speaks about the same one. */
  month: number;
  year: number;
}

// Initial selector options only: the server ships `labels` with every response and
// those win, so the list here cannot drift from what the backend can build.
const FALLBACK_LABELS: Record<string, string> = {
  totals: 'Итоги месяца',
  debtors: 'Должники',
  carryovers: 'Переносы переплаты',
};

/**
 * «Сводка для чата»: markdown the treasurer pastes into the clan chat.
 *
 * Read-only and computed from the same ledger chain as the «Сальдо» tab, so a
 * pasted summary cannot contradict the screen it was taken from. Markdown, not a
 * table: a clan chat renders pipes as a wall of characters.
 */
export function TreasurySummaryPanel({ clanId, month, year }: TreasurySummaryPanelProps) {
  const [kind, setKind] = useState('totals');
  // Сводка — вспомогательный инструмент: свёрнута, пока не нужна. Иначе первый
  // экран «Обзора» занимает текст, который читают раз в день.
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<TreasurySummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    if (!clanId) return;
    setIsLoading(true);
    setError('');
    try {
      setData(await getTreasurySummary(clanId, { month, year, kind }));
    } catch {
      setData(null);
      setError('Не удалось построить сводку');
    } finally {
      setIsLoading(false);
    }
  }, [clanId, month, year, kind]);

  useEffect(() => {
    void load();
  }, [load]);

  const labels = data?.labels || FALLBACK_LABELS;
  const kinds = data?.kinds || Object.keys(FALLBACK_LABELS);

  const handleCopy = async () => {
    if (!data?.markdown) return;
    await copyText(data.markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  if (!clanId) return null;

  return (
    <section className="ts-panel">
      <div className="ts-header">
        <button className="ts-toggle" onClick={() => setOpen((v) => !v)}>
          <span className="ts-chevron" aria-hidden="true">{open ? '▾' : '▸'}</span>
          Сводка для чата
        </button>
        {open && (
        <div className="ts-controls">
          <select
            className="ts-select"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            {kinds.map((code) => (
              <option key={code} value={code}>
                {labels[code] || code}
              </option>
            ))}
          </select>
          <button className="ts-btn" onClick={() => void load()} disabled={isLoading}>
            {isLoading ? 'Считаю…' : 'Обновить'}
          </button>
          <button
            className="ts-btn ts-btn-primary"
            onClick={() => void handleCopy()}
            disabled={!data?.markdown}
          >
            {copied ? 'Скопировано' : 'Скопировать'}
          </button>
        </div>
        )}
      </div>

      {open && (
        <>
      {error && <div className="ts-error">{error}</div>}

      {data?.markdown ? (
        <>
          <pre className="ts-output">{data.markdown}</pre>
          {data.reason === 'no_operations' && (
            <p className="ts-note">
              В казне за этот месяц нет операций — сводка пустая по факту, а не потому что
              данных не нашли.
            </p>
          )}
        </>
      ) : (
        !error && <div className="ts-muted">Загрузка…</div>
      )}
        </>
      )}
    </section>
  );
}
