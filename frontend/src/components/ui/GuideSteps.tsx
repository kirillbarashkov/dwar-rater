import { useState } from 'react';
import './GuideSteps.css';

export interface GuideStep {
  /** Что сделать — простым языком, без бухгалтерских терминов. */
  text: string;
  /** Необязательная кнопка: ведёт туда, где шаг выполняется. */
  action?: { label: string; onClick: () => void };
}

interface GuideStepsProps {
  /** По умолчанию «Что здесь делать». */
  title?: string;
  steps: GuideStep[];
  /** Для плотных форм — свёрнут по умолчанию. */
  defaultOpen?: boolean;
}

/**
 * Пошаговое объяснение «что сделать, чтобы получить результат».
 *
 * Задача — снять страх перед таблицей и цифрами: сначала говорим, зачем этот экран
 * и какие шаги в нём есть, и только потом показываем данные. Текст пишем как
 * инструкцию для человека без бухгалтерского образования, а не как справку.
 */
export function GuideSteps({ title = 'Что здесь делать', steps, defaultOpen = true }: GuideStepsProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={`gs ${open ? 'gs-open' : 'gs-closed'}`}>
      <button className="gs-header" onClick={() => setOpen((value) => !value)}>
        <span className="gs-chevron" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
        <span className="gs-title">{title}</span>
        <span className="gs-count">{steps.length} шагов</span>
      </button>

      {open && (
        <ol className="gs-list">
          {steps.map((step, index) => (
            <li key={index} className="gs-item">
              <span className="gs-num">{index + 1}</span>
              <span className="gs-text">{step.text}</span>
              {step.action && (
                <button className="gs-action" onClick={step.action.onClick}>
                  {step.action.label}
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
