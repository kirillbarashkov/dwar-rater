import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * A35: одна точка для «загрузить данные, при ошибке — пустое значение».
 *
 * Раньше этот паттерн был переписан в каждом компоненте по-своему:
 * `.then(setX).catch(() => setX([]))`, свой `isLoading`, свой повтор при смене
 * ключа. Отличия были случайными: где-то ошибка молчала, где-то оставался
 * старый массив, где-то спиннер не снимался. Одно место — одно поведение.
 *
 * `silent` нужен для обновления после записи: спиннер на весь экран в этот
 * момент размонтирует вкладку, и сообщение об успехе показать некому.
 *
 * Ошибка возвращается, а не проглатывается: вызывающий решает, показать тост
 * или оставить пустой список (см. A20 — там как раз убирали молчание).
 */
export function useAsyncData<T>(
  loader: () => Promise<T>,
  deps: unknown[],
  fallback: T,
  options: { silentFirstLoad?: boolean } = {},
) {
  const [data, setData] = useState<T>(fallback);
  const [isLoading, setIsLoading] = useState(!options.silentFirstLoad);
  const [error, setError] = useState<unknown>(null);
  const firstLoad = useRef(true);

  // Loader держим в ref: у вызывающего он может быть инлайн-стрелкой, и без
  // этого эффект перезапускался бы на каждый рендер.
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const next = await loaderRef.current();
      setData(next);
      setError(null);
      return next;
    } catch (err) {
      setData(fallback);
      setError(err);
      return fallback;
    } finally {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    const silent = options.silentFirstLoad ? false : !firstLoad.current;
    firstLoad.current = false;
    void reload(silent);
  }, [reload, options.silentFirstLoad]);

  return { data, setData, isLoading, error, reload };
}
