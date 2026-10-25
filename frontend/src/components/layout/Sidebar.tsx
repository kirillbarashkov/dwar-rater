import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth, usePermission } from '../../hooks/useAuth';
import { TREASURY_TABS, DEFAULT_CLAN_ID } from '../../utils/constants';
import './Sidebar.css';

interface TabItem {
  key: string;
  label: string;
  icon: string;
}

interface TabGroup {
  key: string;
  label: string;
  icon: string;
  children?: TabItem[];
}

/** Tabs that belong to the treasurer's own section (see navGroups). */
const TREASURY_GROUP_KEY = 'treasury-nav';

interface SidebarProps {
  tabGroups?: TabGroup[];
  activeTab?: string;
  onTabChange?: (groupKey: string, tabKey: string) => void;
  chatOpen?: boolean;
  onToggleChat?: () => void;
}

// Default navigation structure. The treasury lives in its own group: it is a
// different job from clan administration, and its visibility is decided by the
// `treasury` permission group (admin and treasurer), not by being on the clan page.
const navGroups: TabGroup[] = [
  { key: 'clan', label: 'Клан', icon: '🛡️', children: [
    { key: 'info', label: 'Информация', icon: '🛡️' },
    { key: 'members', label: 'Состав', icon: '👥' },
  ]},
  { key: TREASURY_GROUP_KEY, label: 'Казначейство', icon: '💰', children: [
    { key: 'treasury', label: 'Казна', icon: '💰' },
    { key: 'analytics', label: 'Аналитика налогов', icon: '📊' },
    { key: 'treasury-pairs', label: 'Обмены и долги', icon: '⇄' },
    { key: 'member-status', label: 'Статус персонажа', icon: '🧾' },
    { key: 'loans', label: 'Займы из казны', icon: '📉' },
    { key: 'exclusions', label: 'Группы исключений', icon: '🚫' },
    { key: 'treasury-import', label: 'Импорт / Экспорт', icon: '📥' },
  ]},
  { key: 'character', label: 'Персонаж', icon: '🧙', children: [
    { key: 'info', label: 'Информация', icon: '📋' },
    { key: 'combat', label: 'Боевое', icon: '⚔️' },
    { key: 'clan', label: 'Клановое', icon: '🛡️' },
  ]},
  { key: 'analysis', label: 'Анализ персонажа', icon: '📊', children: [
    { key: 'stats', label: 'Характеристики', icon: '📊' },
    { key: 'equipment', label: 'Экипировка', icon: '⚔️' },
    { key: 'effects', label: 'Эффекты', icon: '✨' },
    { key: 'medals', label: 'Медали', icon: '🏅' },
    { key: 'records', label: 'Рекорды', icon: '📜' },
    { key: 'other', label: 'Прочее', icon: '📋' },
    { key: 'closed', label: 'Закрытые', icon: '🔒' },
    { key: 'history', label: 'История слепков', icon: '💾' },
    { key: 'export', label: 'Экспорт', icon: '📤' },
  ]},
  { key: 'track', label: 'Трек улучшений', icon: '📈', children: [
    { key: 'track', label: 'Трек', icon: '📈' },
    { key: 'compare-list', label: 'Мой список', icon: '📋' },
    { key: 'compare', label: 'Сравнить персонажей', icon: '⚖️' },
  ]},
  { key: 'about', label: 'О проекте', icon: '📘' },
  { key: 'chat', label: 'Чат', icon: '💬' },
];



export function Sidebar({
  tabGroups = navGroups,
  activeTab,
  onTabChange,
  chatOpen = false,
  onToggleChat,
}: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const canAccessAdmin = usePermission('admin', 'read') === 'full';
  // The treasury section is for admin and treasurer. Everyone else still SEES the
  // tab — greyed out with an explanation — so the feature is discoverable and the
  // reason for its absence is obvious rather than mysterious.
  const canTreasury = usePermission('treasury', 'read') === 'full';
  // «О проекте» читают все роли (право выдано по умолчанию каждой). Гасим пункт
  // только если роль настраивали вручную и права на рассказ о проекте не дали —
  // иначе была бы невнятная ошибка вместо объяснения.
  const canAbout = usePermission('about', 'read') !== 'none';
  // Ворота привязки (решение пользователя): пока персонаж не привязан, остальные
  // фичи недоступны — пользователь остаётся на «Персонаж → Информация» и
  // привязывает персонажа. Чат не блокируем: он не про персонажа.
  const { user } = useAuth();
  const noBinding = !user?.character_url;
  const isGroupDisabled = (group: TabGroup) =>
    (group.key === TREASURY_GROUP_KEY && !canTreasury) ||
    (group.key === 'about' && !canAbout) ||
    // Ворота привязки не распространяются на «О проекте»: это рассказ о проекте,
    // он нужен и до того, как персонаж привязан (чат не блокируем по той же причине).
    (noBinding && group.key !== 'character' && group.key !== 'chat' && group.key !== 'about');
  // Раскрытие и подсветка выводятся из АДРЕСА, а не из локального состояния.
  // Раньше клик по разделу, содержимое которого рендерит другая страница, применял
  // состояние к уходящему экземпляру сайдбара (у каждой страницы своя раскладка),
  // а смонтированный заново инициализировался из пути: «Казначейство» на
  // /clan/2315 подсвечивало ещё и «Клан».
  const urlTab = new URLSearchParams(location.search).get('tab') || '';
  const groupForTab = (tab: string): string => {
    if (!tab) return '';
    if (TREASURY_TABS.includes(tab)) return TREASURY_GROUP_KEY;
    if (['track', 'compare', 'compare-list'].includes(tab)) return 'track';
    if (['stats', 'equipment', 'effects', 'medals', 'records', 'other', 'closed', 'history', 'export'].includes(tab)) return 'analysis';
    // Ключи 'info'/'clan' есть и у клана, и у персонажа — различаем по пути.
    if (location.pathname.startsWith('/character')) return 'character';
    if (location.pathname.startsWith('/clan')) return 'clan';
    return '';
  };
  // Ручное раскрытие/сворачивание пользователем. Значение по умолчанию — из адреса,
  // поэтому подсветка и раскрытие не расходятся между экземплярами сайдбара (у каждой
  // страницы своя раскладка). В эффекте это держать нельзя: setState в эффекте даёт
  // каскадные перерисовки (правило react-hooks), а при перемонтировании состояние
  // всё равно сбрасывалось — отсюда и бралась двойная подсветка.
  const [manualGroup, setManualGroup] = useState<string | null>(null);
  const expandedGroup = manualGroup ??
    (groupForTab(urlTab) ||
     (location.pathname.startsWith('/clan') ? 'clan'
     : location.pathname.startsWith('/character') ? 'character'
     : 'analysis'));
  const isClanPage = location.pathname.startsWith('/clan');
  const isCharacterPage = location.pathname.startsWith('/character');
  // Главная страница несёт «Анализ персонажа» и «Трек улучшений»: без этого флага
  // клик по пункту «Трека» с клановой страницы не делал перехода.
  const isHomePage = location.pathname === '/';
  const isAboutPage = location.pathname.startsWith('/about');
  // Активная группа — тоже производная адреса: она решает и подсветку раздела,
  // и подсветку подпункта (иначе 'info' подсвечивался сразу в двух группах).
  const activeGroupKey =
    groupForTab(urlTab) ||
    (isClanPage ? 'clan' : isCharacterPage ? 'character' : isAboutPage ? 'about' : isHomePage ? 'analysis' : '');

  const handleGroupClick = (groupKey: string, children?: TabItem[], disabled = false) => {
    if (disabled) return;
    if (children && children.length > 0) {
      const willExpand = expandedGroup !== groupKey;
      setManualGroup(willExpand ? groupKey : '');
      if (willExpand && groupKey === 'clan') {
        // Переход обязателен ВСЕГДА, а не только с чужой страницы: подсветка
        // сайдбара выводится из адреса, поэтому без navigate адрес не менялся и
        // фокус оставался на прежнем разделе («Клан» ↔ «Казначейство»).
        navigate(`/clan/${DEFAULT_CLAN_ID}?tab=${children[0]?.key || 'info'}`);
      } else if (willExpand && groupKey === TREASURY_GROUP_KEY) {
        // Содержимое «Казначейства» рендерит раскладка клановой страницы, а её
        // вкладка живёт в адресе. Раньше переход был только с чужой страницы —
        // из-за этого баг воспроизводился лишь при «Клан → Казначейство».
        navigate(`/clan/${DEFAULT_CLAN_ID}?tab=${children[0]?.key || 'treasury'}`);
      } else if (willExpand && groupKey === 'character' && !isCharacterPage) {
        navigate('/character');
      } else if (willExpand && groupKey === 'analysis' && (isClanPage || isCharacterPage)) {
        navigate('/');
      } else if (willExpand && groupKey === 'track') {
        navigate('/?tab=track');
      }
      onTabChange?.(groupKey, children[0].key);
    } else if (groupKey === 'chat') {
      onToggleChat?.();
    } else if (groupKey === 'track') {
      navigate('/?tab=track');
    } else if (groupKey === 'about') {
      navigate('/about');
    }
  };

  const handleTabClick = (groupKey: string, tabKey: string) => {
    setManualGroup(groupKey);
    // Пункт раздела может жить на другой странице. Без перехода клик менял только
    // состояние: на чужой странице либо ничего не происходило, либо оставался
    // пустой экран (как с «Казначейством» и «Треком улучшений»).
    if (groupKey === 'clan' || groupKey === TREASURY_GROUP_KEY) {
      // Всегда, даже находясь на клановой странице: иначе адрес не меняется и
      // подсветка раздела остаётся на прежнем пункте.
      navigate(`/clan/${DEFAULT_CLAN_ID}?tab=${tabKey}`);
    } else if (groupKey === 'character' && !isCharacterPage) {
      navigate('/character');
    } else if (groupKey === 'track' && !isHomePage) {
      navigate(`/?tab=${tabKey}`);
    }
    onTabChange?.(groupKey, tabKey);
  };

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        <div className="sidebar-section">
          <span className="sidebar-section-title">Навигация</span>
          {tabGroups.map((group) => {
            const groupDisabled = isGroupDisabled(group);
            const isActive = group.key === activeGroupKey ||
                            (group.key === 'chat' && chatOpen);
            const hint = groupDisabled
              ? (group.key === 'about'
                  ? 'Нет права на раздел «О проекте»'
                  : noBinding && group.key !== TREASURY_GROUP_KEY
                    ? 'Привяжите персонажа, чтобы открыть раздел'
                    : 'Доступно админу и казначею')
              : undefined;
            return (
              <div key={group.key}>
                <button
                  className={`sidebar-item ${isActive ? 'active' : ''} ${groupDisabled ? 'sidebar-item-disabled' : ''}`}
                  onClick={() => handleGroupClick(group.key, group.children, groupDisabled)}
                  disabled={groupDisabled}
                  title={hint}
                >
                  <span className="sidebar-icon">{group.icon}</span>
                  <span>{group.label}</span>
                </button>
                {group.children && (
                  <div className={`sidebar-children ${expandedGroup === group.key ? '' : 'collapsed'}`}>
                    <div>
                    {group.children.map((tab) => (
                      <button
                        key={tab.key}
                        className={`sidebar-item ${activeTab === tab.key && group.key === activeGroupKey ? 'active' : ''} ${groupDisabled ? 'sidebar-item-disabled' : ''}`}
                        onClick={() => handleTabClick(group.key, tab.key)}
                        disabled={groupDisabled}
                        title={hint}
                      >
                        <span className="sidebar-icon">{tab.icon}</span>
                        <span>{tab.label}</span>
                      </button>
                    ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </nav>
      {canAccessAdmin && (
        <div className="sidebar-admin">
          <button
            className={`sidebar-item ${location.pathname === '/admin' ? 'active' : ''}`}
            onClick={() => navigate('/admin')}
          >
            <span className="sidebar-icon">⚙️</span>
            <span>Админка</span>
          </button>
        </div>
      )}
    </aside>
  );
}
