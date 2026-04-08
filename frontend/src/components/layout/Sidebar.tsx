import { useNavigate, useLocation } from 'react-router-dom';
import './Sidebar.css';

interface TabItem {
  key: string;
  label: string;
  icon: string;
}

interface SidebarProps {
  tabs?: TabItem[];
  activeTab?: string;
  onTabChange?: (tabKey: string) => void;
  chatOpen?: boolean;
  onToggleChat?: () => void;
  showTabs?: boolean;
}

const defaultTabs: TabItem[] = [
  { key: 'stats', label: 'Характеристики', icon: '📊' },
  { key: 'equipment', label: 'Экипировка', icon: '⚔️' },
  { key: 'effects', label: 'Эффекты', icon: '✨' },
  { key: 'medals', label: 'Медали', icon: '🏅' },
  { key: 'records', label: 'Рекорды', icon: '📜' },
  { key: 'other', label: 'Прочее', icon: '📋' },
  { key: 'track', label: 'Трек улучшений', icon: '📈' },
];

export function Sidebar({
  tabs = defaultTabs,
  activeTab,
  onTabChange,
  chatOpen = false,
  onToggleChat,
  showTabs = false,
}: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const isClanPage = location.pathname.startsWith('/clan');

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        <div className="sidebar-section">
          <span className="sidebar-section-title">Навигация</span>
          <button
            className={`sidebar-item ${isClanPage ? 'active' : ''}`}
            onClick={() => navigate('/clan/2315')}
            title="Орден Чести"
          >
            <span className="sidebar-icon">🛡️</span>
            <span>Клан</span>
          </button>
          <button
            className={`sidebar-item ${chatOpen ? 'active' : ''}`}
            onClick={onToggleChat}
            title="Клановый чат"
          >
            <span className="sidebar-icon">💬</span>
            <span>Чат</span>
          </button>
        </div>

        {showTabs && (
          <div className="sidebar-section">
            <span className="sidebar-section-title">Вкладки</span>
            {tabs.map((tab) => (
              <button
                key={tab.key}
                className={`sidebar-item ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => onTabChange?.(tab.key)}
              >
                <span className="sidebar-icon">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        )}
      </nav>
    </aside>
  );
}
