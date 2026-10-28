/**
 * Тема интерфейса: единственное место, где она читается, пишется и применяется.
 *
 * До этого `data-theme` на `<html>` выставлял только `Header`, поэтому
 * самостоятельные страницы (`/admin`, `/about`) рендерились в теме по умолчанию:
 * при сохранённой светлой теме `/admin` оставался тёмным. В `AboutPage` логика
 * была продублирована копией — то есть новых страниц это не спасало.
 */

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'theme';

/** Сохранённый выбор пользователя, иначе системная настройка. */
export function preferredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_KEY, theme);
}

/**
 * Применяет тему до первого рендера. Вызывается один раз в `main.tsx`:
 * страница, которая не рендерит `Header`, больше не остаётся без темы.
 */
export function initTheme(): Theme {
  const theme = preferredTheme();
  applyTheme(theme);
  return theme;
}
