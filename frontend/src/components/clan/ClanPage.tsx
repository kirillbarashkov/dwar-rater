import { Tabs, TabPanel } from '../ui/Tabs';
import { ClanHeader } from './ClanHeader';
import { ClanMembersTable } from './ClanMembersTable';
import './ClanPage.css';

interface ClanPageProps {
  clanId: number;
}

export function ClanPage({ clanId }: ClanPageProps) {
  const tabs = [
    { key: 'info', label: 'Информация' },
    { key: 'members', label: 'Состав' },
  ];

  return (
    <div className="clan-page">
      <Tabs tabs={tabs} defaultTab="info">
        <TabPanel tabKey="info" activeTab="info">
          <ClanHeader clanId={clanId} />
        </TabPanel>
        <TabPanel tabKey="members" activeTab="members">
          <ClanMembersTable clanId={clanId} />
        </TabPanel>
      </Tabs>
    </div>
  );
}
