import type { AnalysisResult, FlashvarsExtra, PersonalInfo } from '../../types/character';
import { Button } from '../ui/Button';
import { StatGroup } from '../ui/StatGroup';
import { ClosedProfileBanner } from '../snapshots/ClosedProfileBanner';
import { usePermission } from '../../hooks/useAuth';
import './CharacterInfoTab.css';

interface CharacterInfoTabProps {
  character: AnalysisResult | null;
  fetchedAt: Date | null;
  onRefresh: () => void;
  refreshing: boolean;
}

function ProgressBar({ label, current, max, color }: { label: string; current: string; max: string; color: string }) {
  const cur = parseInt(current, 10) || 0;
  const mx = parseInt(max, 10) || 1;
  const percent = Math.min(100, Math.round((cur / mx) * 100));
  return (
    <div className="char-info-progress">
      <div className="char-info-progress-header">
        <span className="char-info-progress-label">{label}</span>
        <span className="char-info-progress-value">{cur} / {mx}</span>
      </div>
      <div className="char-info-progress-bar">
        <div className="char-info-progress-fill" style={{ width: `${percent}%`, background: color }} />
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="char-info-row">
      <span className="char-info-row-label">{label}</span>
      <span className="char-info-row-value">{value}</span>
    </div>
  );
}

export function CharacterInfoTab({ character, fetchedAt, onRefresh, refreshing }: CharacterInfoTabProps) {
  const canWrite = usePermission('character', 'write') === 'full';

  if (!character) return null;

  if (character.profile_closed) {
    return (
      <div className="char-info-tab">
        <ClosedProfileBanner character={character} />
        {canWrite && (
          <div className="char-info-actions">
            <Button variant="ghost" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? 'Обновление...' : '🔄 Обновить данные'}
            </Button>
          </div>
        )}
      </div>
    );
  }

  const fv: FlashvarsExtra | undefined = character.flashvars_extra;
  const pi: PersonalInfo | undefined = character.personal_info;
  const isOnline = fv?.online === '1';
  const genderLabel = fv?.gender === '1' ? 'Женский' : fv?.gender === '0' ? 'Мужской' : null;
  const profEntries = Object.entries(character.professions || {});

  return (
    <div className="char-info-tab">
      {/* Hero-блок */}
      <div className="char-info-hero">
        <div className="char-info-hero-icon">🧙</div>
        <div className="char-info-hero-main">
          <h1 className="char-info-hero-name">{character.name}</h1>
          <div className="char-info-hero-tags">
            {character.race && <span className="char-info-tag">{character.race}</span>}
            {character.level && <span className="char-info-tag">Ур. {character.level}</span>}
            {character.rank && <span className="char-info-tag">⚔️ {character.rank}</span>}
            {isOnline && <span className="char-info-tag char-info-tag-online">● В сети</span>}
          </div>
          {character.clan && (
            <div className="char-info-hero-clan">
              <span className="char-info-clan-name">🛡️ {character.clan}</span>
              {character.clan_rank && <span className="char-info-clan-rank">{character.clan_rank}</span>}
            </div>
          )}
        </div>
        {canWrite && (
          <div className="char-info-hero-actions">
            <Button variant="ghost" onClick={onRefresh} disabled={refreshing} title="Принудительно обновить с dwar.ru">
              {refreshing ? '⏳' : '🔄 Обновить'}
            </Button>
          </div>
        )}
      </div>

      {/* HP/MP полоски */}
      {fv && (fv.hp || fv.hpMax) && (
        <div className="char-info-vitals">
          <ProgressBar label="❤️ Здоровье" current={fv.hp} max={fv.hpMax} color="linear-gradient(90deg, #ff5555, #ff8888)" />
          <ProgressBar label="🔵 Мана" current={fv.mp} max={fv.mpMax} color="linear-gradient(90deg, #50d4ff, #80c8ff)" />
        </div>
      )}

      {/* Локация / маунт / пол */}
      {fv && (fv.tTown || fv.tLocation || fv.mount || genderLabel) && (
        <div className="char-info-status-grid">
          {fv.tLocation && <InfoRow label="Локация" value={fv.tLocation} />}
          {fv.tTown && fv.tTown !== fv.tLocation && <InfoRow label="Город" value={fv.tTown} />}
          {fv.mount && <InfoRow label="Маунт" value={fv.mount} />}
          {genderLabel && <InfoRow label="Пол" value={genderLabel} />}
        </div>
      )}

      {/* Боевые результаты KPI */}
      <div className="char-info-kpi-grid">
        <div className="char-info-kpi-card">
          <span className="char-info-kpi-label">Победы</span>
          <span className="char-info-kpi-value char-info-kpi-win">{character.wins}</span>
        </div>
        <div className="char-info-kpi-card">
          <span className="char-info-kpi-label">Поражения</span>
          <span className="char-info-kpi-value char-info-kpi-lose">{character.losses}</span>
        </div>
        <div className="char-info-kpi-card">
          <span className="char-info-kpi-label">Винрейт</span>
          <span className="char-info-kpi-value">{character.winrate}%</span>
        </div>
        {character.kills && (
          <div className="char-info-kpi-card">
            <span className="char-info-kpi-label">Убийства</span>
            <span className="char-info-kpi-value">{character.kills}</span>
          </div>
        )}
      </div>

      {/* Профессии */}
      {profEntries.length > 0 && (
        <StatGroup title="Профессии" stats={character.professions} />
      )}

      {/* Персональная информация */}
      {pi && (
        <div className="stat-group">
          <h3 className="stat-group-title">Персональная информация</h3>
          <table className="stat-table">
            <tbody>
              {pi['Имя'] && (
                <tr><td className="stat-label">Имя</td><td className="stat-value">{pi['Имя']}</td></tr>
              )}
              {pi['Обитает в мире Фэо'] && (
                <tr><td className="stat-label">Обитает в мире Фэо</td><td className="stat-value">{pi['Обитает в мире Фэо']}</td></tr>
              )}
              {pi['День рождения'] && (
                <tr><td className="stat-label">День рождения</td><td className="stat-value">{pi['День рождения']}</td></tr>
              )}
              {pi['О себе'] && (
                <tr><td className="stat-label">О себе</td><td className="stat-value">{pi['О себе']}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Поместье */}
      {character.manor_location && (
        <div className="stat-group">
          <h3 className="stat-group-title">Поместье</h3>
          <table className="stat-table">
            <tbody>
              <tr><td className="stat-label">Локация</td><td className="stat-value">{character.manor_location}</td></tr>
              {character.manor_buildings.length > 0 && (
                <tr><td className="stat-label">Построек</td><td className="stat-value">{character.manor_buildings.length}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Метаданные + ссылка на полный анализ */}
      <div className="char-info-footer">
        {fetchedAt && (
          <span className="char-info-fetched">
            Данные от {fetchedAt.toLocaleString('ru-RU')}
          </span>
        )}
        <a
          className="char-info-full-link"
          href={`/?analyze=${encodeURIComponent(`https://w1.dwar.ru/user_info.php?nick=${encodeURIComponent(character.name)}`)}`}
        >
          Открыть полный анализ →
        </a>
      </div>
    </div>
  );
}
