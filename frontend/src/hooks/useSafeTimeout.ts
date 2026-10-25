import { useCallback, useEffect, useRef } from 'react';

/**
 * A51: таймер, который отменяется при размонтировании.
 *
 * Раньше в шести местах стояло `setTimeout(() => setCopyStatus(null), 2000)` без
 * сохранения id: cleanup в эффекте отменить такой таймер не мог. Последствия —
 * таймер живёт после ухода со страницы, а `setState` приходит в уже
 * размонтированный компонент (в React 19 это не предупреждение, а тихий no-op,
 * но логика «статус скопировано» обновляет то, чего уже нет).
 *
 * Возвращает функцию `schedule(fn, ms)`: предыдущий таймер отменяется, новый
 * взводится; при размонтировании отменяется последний.
 */
export function useSafeTimeout() {
  const timerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    },
    [],
  );

  return useCallback((fn: () => void, ms: number) => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
    }
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      fn();
    }, ms);
  }, []);
}
