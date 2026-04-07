import { useState, createContext, useContext, type ReactNode } from 'react';
import './Tabs.css';

interface Tab {
  key: string;
  label: string;
}

interface TabsContextValue {
  activeTab: string;
}

const TabsContext = createContext<TabsContextValue>({ activeTab: '' });

interface TabsProps {
  tabs: Tab[];
  children: ReactNode;
  defaultTab?: string;
}

export function Tabs({ tabs, children, defaultTab }: TabsProps) {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.key || '');

  return (
    <TabsContext.Provider value={{ activeTab }}>
      <div className="tabs-container">
        <div className="tabs-header">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`tab-button ${activeTab === tab.key ? 'tab-button-active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="tabs-content">
          {children}
        </div>
      </div>
    </TabsContext.Provider>
  );
}

interface TabPanelProps {
  tabKey: string;
  children: ReactNode;
}

export function TabPanel({ tabKey, children }: TabPanelProps) {
  const { activeTab } = useContext(TabsContext);
  if (tabKey !== activeTab) return null;
  return <div className="tab-panel">{children}</div>;
}
