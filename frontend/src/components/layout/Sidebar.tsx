import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
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

interface SidebarProps {
  tabGroups?: TabGroup[];
  activeTab?: string;
  onTabChange?: (groupKey: string, tabKey: string) => void;
  chatOpen?: boolean;
  onToggleChat?: () => void;
}

// Default navigation structure
const navGroups: TabGroup[] = [
  { key: 'clan', label: 'Клан', icon: '🛡️', children: [
    { key: 'info', label: 'Информация', icon: '🛡️' },
    { key: 'members', label: 'Состав', icon: '👥' },
    { key: 'treasury', label: 'Казна', icon: '💰' },
    { key: 'analytics', label: 'Аналитика', icon: '📊' },
    { key: 'treasury-import', label: 'Импорт / Экспорт', icon: '📥' },
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
  const { user } = useAuth();
  const [expandedGroup, setExpandedGroup] = useState<string>(() => 
    location.pathname.startsWith('/clan') ? 'clan' : 'analysis'
  );
  const isClanPage = location.pathname.startsWith('/clan');
  const isAnalyzePage = location.pathname.startsWith('/analyze');

  const handleGroupClick = (groupKey: string, children?: TabItem[]) => {
    if (children && children.length > 0) {
      const willExpand = expandedGroup !== groupKey;
      setExpandedGroup(willExpand ? groupKey : '');
      if (willExpand && groupKey === 'clan' && !isClanPage) {
        navigate('/clan/2315');
      } else if (willExpand && groupKey === 'analysis' && isClanPage) {
        navigate('/');
      } else if (willExpand && groupKey === 'track') {
        navigate('/');
      }
      onTabChange?.(groupKey, children[0].key);
    } else if (groupKey === 'chat') {
      onToggleChat?.();
    } else if (groupKey === 'track') {
      navigate('/');
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
            const isActive = isClanPage && group.key === 'clan' || 
                            (group.key === 'analysis' && isAnalyzePage) ||
                            (group.key === 'chat' && chatOpen);
            return (
              <div key={group.key}>
                <button
                  className={`sidebar-item ${isActive || expandedGroup === group.key ? 'active' : ''}`}
                  onClick={() => handleGroupClick(group.key, group.children)}
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
                        className={`sidebar-item ${activeTab === tab.key ? 'active' : ''}`}
                        onClick={() => handleTabClick(group.key, tab.key)}
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
      {user?.role === 'admin' && (
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
