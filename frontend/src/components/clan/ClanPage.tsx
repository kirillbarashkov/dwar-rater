import { Tabs, TabPanel } from '../ui/Tabs';
import { ClanHeader } from './ClanHeader';
import { ClanMembersTable } from './ClanMembersTable';
import { ClanHierarchy } from './ClanHierarchy';
import './ClanPage.css';

interface ClanPageProps {
  clanId: number;
}

export function ClanPage({ clanId }: ClanPageProps) {
  const tabs = [
    { key: 'info', label: 'Информация' },
    { key: 'members', label: 'Состав' },
    { key: 'hierarchy', label: 'Иерархия' },
  ];

  return (
    <div className="clan-page">
      <Tabs tabs={tabs} defaultTab="info">
        <TabPanel tabKey="info">
          <ClanHeader clanId={clanId} />
        </TabPanel>
        <TabPanel tabKey="members">
          <ClanMembersTable clanId={clanId} />
        </TabPanel>
        <TabPanel tabKey="hierarchy">
          <ClanHierarchy clanId={clanId} />
        </TabPanel>
      </Tabs>
    </div>
  );
}
