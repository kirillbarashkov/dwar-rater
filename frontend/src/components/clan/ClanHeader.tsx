import { useState, useEffect } from 'react';
import type { ClanInfoData } from '../../types/clanInfo';
import { getClanInfo } from '../../api/clanInfo';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import './ClanHeader.css';

interface ClanHeaderProps {
  clanId: number;
}

export function ClanHeader({ clanId }: ClanHeaderProps) {
  const [info, setInfo] = useState<ClanInfoData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    getClanInfo(clanId)
      .then(setInfo)
      .catch(() => setInfo(null))
      .finally(() => setIsLoading(false));
  }, [clanId]);

  if (isLoading) return <LoadingSpinner />;
  if (!info) return <p className="clan-error">Не удалось загрузить информацию о клане</p>;

  return (
    <div className="clan-header">
      <div className="clan-logo-section">
        {info.logo_url && (
          <img
            className="clan-logo"
            src={`https://w1.dwar.ru/${info.logo_url}`}
            alt={info.name}
          />
        )}
        <div className="clan-title-section">
          <h2 className="clan-name">{info.name}</h2>
          <div className="clan-status">
            {info.clan_rank && <span className="clan-badge">{info.clan_rank}</span>}
            {info.clan_level > 0 && <span className="clan-level">Уровень {info.clan_level}</span>}
            {info.step > 0 && <span className="clan-step">Ступень {info.step}</span>}
            {info.talents > 0 && <span className="clan-talents">{info.talents} ★ таланты</span>}
          </div>
          {info.leader_nick && (
            <div className="clan-leader">
              Глава: <strong>{info.leader_nick}</strong> [{info.leader_rank}]
            </div>
          )}
        </div>
      </div>
      {info.description && (
        <p className="clan-description">{info.description}</p>
      )}
    </div>
  );
}
