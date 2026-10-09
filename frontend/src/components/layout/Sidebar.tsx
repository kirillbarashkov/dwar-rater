import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { usePermission } from '../../hooks/useAuth';
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
const TREASURY_TABS = ['treasury', 'analytics', 'treasury-import'];

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
  const isGroupDisabled = (group: TabGroup) =>
    group.key === TREASURY_GROUP_KEY && !canTreasury;
  const [expandedGroup, setExpandedGroup] = useState<string>(() =>
    location.pathname.startsWith('/clan') ? 'clan'
    : location.pathname.startsWith('/character') ? 'character'
    : 'analysis'
  );
  const isClanPage = location.pathname.startsWith('/clan');
  const isCharacterPage = location.pathname.startsWith('/character');
  const isAnalyzePage = location.pathname.startsWith('/analyze');

  const handleGroupClick = (groupKey: string, children?: TabItem[], disabled = false) => {
    if (disabled) return;
    if (children && children.length > 0) {
      const willExpand = expandedGroup !== groupKey;
      setExpandedGroup(willExpand ? groupKey : '');
      if (willExpand && groupKey === 'clan' && !isClanPage) {
        navigate('/clan/2315');
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
    }
  };

  const handleTabClick = (groupKey: string, tabKey: string) => {
    setExpandedGroup(groupKey);
    onTabChange?.(groupKey, tabKey);
  };

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        <div className="sidebar-section">
          <span className="sidebar-section-title">Навигация</span>
          {tabGroups.map((group) => {
            const groupDisabled = isGroupDisabled(group);
            // On the clan page the treasury is its own section: highlight it (and
            // not «Клан») while one of its tabs is open.
            const inTreasurySection =
              isClanPage && Boolean(activeTab) && TREASURY_TABS.includes(activeTab as string);
            const isActive = (isClanPage && group.key === 'clan' && !inTreasurySection) ||
                            (isClanPage && group.key === TREASURY_GROUP_KEY && inTreasurySection) ||
                            (isCharacterPage && group.key === 'character') ||
                            (group.key === 'analysis' && isAnalyzePage) ||
                            (group.key === 'chat' && chatOpen);
            const hint = groupDisabled ? 'Доступно админу и казначею' : undefined;
            return (
              <div key={group.key}>
                <button
                  className={`sidebar-item ${isActive || expandedGroup === group.key ? 'active' : ''} ${groupDisabled ? 'sidebar-item-disabled' : ''}`}
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
                        className={`sidebar-item ${activeTab === tab.key ? 'active' : ''} ${groupDisabled ? 'sidebar-item-disabled' : ''}`}
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
