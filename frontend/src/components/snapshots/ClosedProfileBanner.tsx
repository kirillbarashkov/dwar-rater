import { useState } from 'react';
import type { AnalysisResult } from '../../types/character';
import { addClosedProfile } from '../../api/closedProfiles';
import { showToast } from '../ui/Toast';
import './ClosedProfileBanner.css';

const GAME_RANKS: Record<number, string> = {
  1: 'Рекрут',
  2: 'Солдат',
  3: 'Боец',
  4: 'Воин',
  5: 'Элитный воин',
  6: 'Чемпион',
  7: 'Гладиатор',
  8: 'Полководец',
  9: 'Мастер войны',
  10: 'Герой',
  11: 'Военный эксперт',
  12: 'Магистр войны',
  13: 'Вершитель',
  14: 'Высший магистр',
  15: 'Повелитель',
  16: 'Легендарный завоеватель',
  17: 'Властелин боя',
  18: 'Победоносец',
  19: 'Триумфатор',
  20: 'Избранник богов',
};

interface ClosedProfileBannerProps {
  character: AnalysisResult;
}

export function ClosedProfileBanner({ character }: ClosedProfileBannerProps) {
  const closedInfo = character.closed_info;
  const rankId = closedInfo?.rank ? parseInt(closedInfo.rank, 10) : null;
  const gameRank = rankId ? GAME_RANKS[rankId] : null;
  const [isAdding, setIsAdding] = useState(false);
  const [isAdded, setIsAdded] = useState(false);
  const [scannedOpenAt, setScannedOpenAt] = useState<string | null>(null);

  const handleAdd = async () => {
    if (!character.name || character.name === 'Unknown') return;
    setIsAdding(true);
    try {
      const result = await addClosedProfile(character.name);
      if ('exists' in result) {
        if (result.is_scanned_open && result.scanned_open_at) {
          setScannedOpenAt(result.scanned_open_at);
          showToast(`Персонаж уже отсканирован открытым ${new Date(result.scanned_open_at).toLocaleDateString('ru-RU')}`, 'info');
        } else {
          showToast('Персонаж уже в списке закрытых', 'warning');
        }
        setIsAdded(true);
      } else {
        showToast(`Персонаж ${character.name} добавлен в закрытые`, 'success');
        setIsAdded(true);
      }
    } catch {
      showToast('Ошибка при добавлении', 'error');
    } finally {
      setIsAdding(false);
    }
  };

  return (
    <div className="closed-profile-banner">
      <div className="cpb-icon">🔒</div>
      <div className="cpb-content">
        <div className="cpb-header">
          <div className="cpb-name">{character.name}</div>
          <div className="cpb-header-right">
            {!isAdded && (
              <button
                className="cpb-add-btn"
                onClick={handleAdd}
                disabled={isAdding}
              >
                {isAdding ? 'Добавление...' : '+ В закрытые'}
              </button>
            )}
            {isAdded && scannedOpenAt && (
              <span className="cpb-added-chip">
                ✓ Отсканирован открытым {new Date(scannedOpenAt).toLocaleDateString('ru-RU')}
              </span>
            )}
            {isAdded && !scannedOpenAt && (
              <span className="cpb-added-chip">✓ В списке закрытых</span>
            )}
          </div>
        </div>
        <div className="cpb-message">
          Профиль персонажа закрыт. Доступна только основная информация.
        </div>
        {closedInfo && (
          <div className="cpb-meta">
            {closedInfo.level && (
              <span className="cpb-meta-item">
                Уровень: <strong>{closedInfo.level}</strong>
              </span>
            )}
            {gameRank && (
              <span className="cpb-meta-item">
                Звание: <strong>{gameRank}</strong>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
