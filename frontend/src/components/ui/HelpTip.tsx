import { useRef, useState, type ReactNode } from 'react';
import { GLOSSARY, type TermCode } from '../../utils/glossary';
import './HelpTip.css';

interface HelpTipProps {
  term: TermCode;
  /** Заголовок может быть короче словарного (например, в шапке таблицы). */
  children?: ReactNode;
  /** Показывать маркер ⓘ (в шапках таблиц он мешает — можно выключить). */
  marker?: boolean;
  /** Выключить открытие по клику (когда клик по слову должен делать другое). */
  clickToToggle?: boolean;
}

/**
 * Подсказка у самого слова, а не в справке «где-то там»: пользователи раздела не
 * бухгалтеры, поэтому объяснение должно быть в одной секунде от вопроса.
 *
 * Открывается наведением, фокусом с клавиатуры и по клику (клик — чтобы работало
 * на планшете и чтобы подсказку можно было «закрепить», не удерживая курсор).
 */
export function HelpTip({ term, children, marker = true, clickToToggle = true }: HelpTipProps) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const anchor = useRef<HTMLSpanElement>(null);
  const entry = GLOSSARY[term];

  // The popup is positioned `fixed` on purpose: the table it usually sits in lives
  // inside a scroll container with `overflow: auto`, which would clip an absolutely
  // positioned tooltip. Coordinates are measured when it opens and clamped to the
  // viewport, so a popup near the right edge stays readable.
  const show = () => {
    const rect = anchor.current?.getBoundingClientRect();
    if (rect) {
      const width = 300;
      setCoords({
        top: Math.min(rect.bottom + 6, window.innerHeight - 40),
        left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 12)),
      });
    }
    setOpen(true);
  };

  const hide = () => {
    setOpen(false);
    setCoords(null);
  };

  return (
    <span
      ref={anchor}
      className="ht"
      tabIndex={0}
      role="note"
      aria-label={`${entry.label}: ${entry.short}`}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      onClick={(event) => {
        if (!clickToToggle) return;
        event.stopPropagation();
        if (open) {
          hide();
        } else {
          show();
        }
      }}
    >
      <span className="ht-label">{children ?? entry.label}</span>
      {marker && (
        <span className="ht-marker" aria-hidden="true">
          ?
        </span>
      )}
      {open && coords && (
        <span className="ht-popup" role="tooltip" style={{ top: coords.top, left: coords.left }}>
          <span className="ht-popup-title">{entry.label}</span>
          <span className="ht-popup-line">{entry.short}</span>
          {entry.what && <span className="ht-popup-body">{entry.what}</span>}
          {entry.todo && (
            <span className="ht-popup-todo">
              <b>Что делать:</b> {entry.todo}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
