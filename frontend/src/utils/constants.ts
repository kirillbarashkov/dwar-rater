export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Вкладки казначейского раздела. Живут в общем модуле, а не в Sidebar.tsx: файл
 * компонента не должен экспортировать константы (react-refresh/only-export-components),
 * а список нужен и боковому меню, и клановой странице — по нему она понимает, что
 * пришла открывать именно «Казначейство».
 *
 * ВАЖНО: список читают два места — сайдбар (определяет раздел по адресу, чтобы
 * подсветить пункт) и ClanPageWrapper в App.tsx (выбирает раскладку treasury-nav/clan).
 * Забытая здесь вкладка открывается «как клан»: адрес не меняется, переход не работает.
 * Новую вкладку казны добавлять сюда обязательно.
 */
export const TREASURY_TABS = [
  'treasury',
  'analytics',
  'treasury-pairs',
  'member-status',
  'loans',
  'exclusions',
  'treasury-import',
];

/**
 * A27: клан по умолчанию. Раньше `2315` был вписан в 15 местах трёх файлов —
 * в адресах сайдбара, в дефолтах клановых вкладок и в тексте ошибки.
 * Переопределяется при сборке: VITE_CLAN_ID=1234 npm run build.
 */
export const DEFAULT_CLAN_ID = Number(import.meta.env.VITE_CLAN_ID) || 2315;
