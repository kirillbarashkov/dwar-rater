export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Вкладки казначейского раздела. Живут в общем модуле, а не в Sidebar.tsx: файл
 * компонента не должен экспортировать константы (react-refresh/only-export-components),
 * а список нужен и боковому меню, и клановой странице — по нему она понимает, что
 * пришла открывать именно «Казначейство».
 */
export const TREASURY_TABS = ['treasury', 'analytics', 'treasury-import'];
