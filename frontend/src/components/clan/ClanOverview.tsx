import { useState, useEffect } from 'react';
import type { ClanInfoData, ClanMemberData, ClanStructure } from '../../types/clanInfo';
import { getClanInfo, updateClanInfo, getClanMembers } from '../../api/clanInfo';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import './ClanOverview.css';

interface ClanOverviewProps {
  clanId: number;
  onSwitchTab?: (tab: string) => void;
}

const CLAN_HISTORY = `Держи её, Меллира! Сестрёнка, нет! Она уходит. Удержи её!
– Мне больше нечего ей дать! Она пуста…
Скрижали за спиной, великий Обелиск и Ветер. Проклятье! Это наш единственный, пусть призрачный, но шанс.

Нас Зов собрал. Зов странный, неизбежный. И мы пришли. Костер в ночи… и восемь человек. Свершилось. Значит, это правда. Проклятье. То, что даже старики, проживши век, считали сказкой, прахом, пылью. Все правда, да… Предвечные наш мир не позабыли.

Семь путников укрыла ночь, судьба вела сюда их на победу. А я? Зачем здесь я? Девчонка-зверобой в доспехах медных, что деда знали моего, и временем окрашены в зеленый.

Из братства человек путём добра с неудержимым Эндаргом пришедший. Ремесленник, познавший тайны трав, что сил дают и исцеляют раны. Аристократ в броне Неистовства багряной сидит задумчиво, играя амулетом алым Пещерной альканоры, как камешком речным.

– Удача наша – ты сейчас, сестренка. А завтра нам удача пригодится, как никогда… – последним прибыл витязь, деяниями темными прославлен, и пламя желтое в его глазах янтарных, так схоже с взглядом грозного Дракона.

Все. Мы готовы. Грянул бой. О, как же чувствую я их! Ударов вихри воина подземелий. Меллиры силу, что втекает в нас. Зверьем безумным рвется сквозь надрывный Эйр запретная волшба отшельника.

– Вы выстояли. Вы смогли… — внутри меня звучит Шеары голос, — объединившие лишь все свои пути вы, ввосьмером, на это были бы способны… Эрифариус, крепи союз! Оружие свое все на алтарь Ветров, что привели сюда вас с краёв света. Стираю ваши имена! Скреплен союз обетом! Хранители ветров с путей различных. Отныне и вовек, вы — стая!

И вспыхнул свет. Я под ноги смотрю. Следы зверей у ног моих. Как необычно... Откуда здесь они? И вдруг я понимаю. Следы мои, но я теперь другая.`;

export function ClanOverview({ clanId, onSwitchTab }: ClanOverviewProps) {
  const [info, setInfo] = useState<ClanInfoData | null>(null);
  const [members, setMembers] = useState<ClanMemberData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [editingStructure, setEditingStructure] = useState(false);
  const [editStructure, setEditStructure] = useState<ClanStructure>({});
  const [councilSlots, setCouncilSlots] = useState(4);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    Promise.all([
      getClanInfo(clanId).catch(() => null),
      getClanMembers(clanId).catch(() => []),
    ]).then(([infoData, membersData]) => {
      setInfo(infoData);
      setMembers(membersData || []);
      setIsLoading(false);
    });
  }, [clanId]);

  useEffect(() => {
    if (info?.clan_structure) {
      setEditStructure(JSON.parse(JSON.stringify(info.clan_structure)));
      setCouncilSlots(info.clan_structure.council_slots || 4);
    }
  }, [info]);

  if (isLoading) return <LoadingSpinner />;
  if (!info) return <p className="clan-error">Не удалось загрузить информацию о клане</p>;

  const playerPercent = info.total_players > 0 
    ? Math.round((info.current_players / info.total_players) * 100) 
    : 0;

  const handleAnalyze = (nick: string) => {
    window.location.href = `/?analyze=${encodeURIComponent(`https://w1.dwar.ru/user_info.php?nick=${encodeURIComponent(nick)}`)}`;
  };

  const goToMembers = () => {
    if (onSwitchTab) {
      onSwitchTab('members');
    }
    window.scrollTo(0, 0);
  };

  const structure = info.clan_structure || {};
  
  const historyPreview = CLAN_HISTORY.slice(0, 200);

  const activeMembers = members.filter(m => !m.is_deleted);

  const handleSaveStructure = async () => {
    setIsSaving(true);
    setSaveError('');
    try {
      const structureToSave = {
        ...editStructure,
        council_slots: councilSlots,
      };
      await updateClanInfo(clanId, { clan_structure: structureToSave });
      const refreshed = await getClanInfo(clanId);
      setInfo(refreshed);
      setEditingStructure(false);
    } catch {
      setSaveError('Ошибка при сохранении структуры');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelEdit = () => {
    if (info?.clan_structure) {
      setEditStructure(JSON.parse(JSON.stringify(info.clan_structure)));
      setCouncilSlots(info.clan_structure.council_slots || 4);
    }
    setEditingStructure(false);
    setSaveError('');
  };

  const updateCouncilSlot = (index: number, nick: string) => {
    const council = [...(editStructure.council || [])];
    while (council.length <= index) {
      council.push({ nick: '', description: '' });
    }
    council[index] = { ...council[index], nick };
    setEditStructure({ ...editStructure, council });
  };

  const renderMemberSelect = (value: string, onChange: (nick: string) => void, placeholder: string) => (
    <select className="co-member-select" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{placeholder}</option>
      {activeMembers.map((m) => (
        <option key={m.nick} value={m.nick}>{m.nick}</option>
      ))}
    </select>
  );

  const renderStructureEdit = () => (
    <div className="co-structure-edit">
      {saveError && <div className="co-save-error">{saveError}</div>}

      <div className="co-edit-row">
        <label className="co-edit-label">Глава клана</label>
        <div className="co-edit-value">
          {structure.leader ? (
            <span className="co-edit-current">{structure.leader.nick}</span>
          ) : (
            <span className="co-edit-empty">Не назначен</span>
          )}
        </div>
      </div>

      {structure.deputies && structure.deputies.length > 0 && (
        <div className="co-edit-row">
          <label className="co-edit-label">Зам. главы</label>
          <div className="co-edit-value">
            {structure.deputies.map((d, i) => (
              <span key={i} className="co-edit-current">{d.nick}{i < structure.deputies!.length - 1 ? ', ' : ''}</span>
            ))}
          </div>
        </div>
      )}

      <div className="co-edit-row">
        <label className="co-edit-label">Совет клана ({councilSlots} мест)</label>
        <div className="co-edit-slots">
          <select
            className="co-council-slots-select"
            value={councilSlots}
            onChange={(e) => setCouncilSlots(parseInt(e.target.value))}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
          {Array.from({ length: councilSlots }).map((_, i) => (
            <div key={i} className="co-edit-slot">
              <span className="co-slot-number">{i + 1}.</span>
              {renderMemberSelect(
                editStructure.council?.[i]?.nick || '',
                (nick) => updateCouncilSlot(i, nick),
                '— выбрать —'
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="co-edit-row">
        <label className="co-edit-label">Воевода</label>
        <div className="co-edit-value">
          {renderMemberSelect(
            editStructure.commander?.nick || '',
            (nick) => setEditStructure({ ...editStructure, commander: nick ? { nick, description: '' } : undefined }),
            '— выбрать —'
          )}
        </div>
      </div>

      <div className="co-edit-actions">
        <button className="co-btn-save" onClick={handleSaveStructure} disabled={isSaving}>
          {isSaving ? 'Сохранение...' : 'Сохранить'}
        </button>
        <button className="co-btn-cancel" onClick={handleCancelEdit}>Отмена</button>
      </div>
    </div>
  );

  const renderStructureView = () => (
    <div className="co-structure-tree">
      <div className="co-tree-branch">
        <div className="co-tree-label">Глава клана</div>
        <div className="co-tree-content">
          {structure.leader && (
            <div className="co-tree-member co-tree-leader" onClick={() => handleAnalyze(structure.leader!.nick)}>
              <span className="co-member-icon">👑</span>
              <span className="co-member-nick">{structure.leader!.nick}</span>
              {structure.leader!.description && (
                <span className="co-member-desc"> — {structure.leader!.description}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {structure.deputies && structure.deputies.length > 0 && (
        <div className="co-tree-branch">
          <div className="co-tree-label co-tree-label-nested">Зам. главы</div>
          <div className="co-tree-content co-tree-content-nested">
            {structure.deputies.map((deputy, index) => (
              <div key={index} className="co-tree-member" onClick={() => handleAnalyze(deputy.nick)}>
                <span className="co-member-icon">
                  {deputy.nick === 'Hozaika ozer' ? '💖' : deputy.nick === 'прото' ? '💰' : '⚔️'}
                </span>
                <span className="co-member-nick">{deputy.nick}</span>
                {deputy.description && (
                  <span className="co-member-desc"> — {deputy.description}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {structure.council && structure.council.length > 0 && (
        <div className="co-tree-branch">
          <div className="co-tree-label co-tree-label-nested">Совет клана</div>
          <div className="co-tree-content co-tree-content-nested">
            {structure.council.map((member, index) => (
              <div key={index} className="co-tree-member" onClick={() => handleAnalyze(member.nick)}>
                <span className="co-member-icon">🎓</span>
                <span className="co-member-nick">{member.nick}</span>
                {member.description && (
                  <span className="co-member-desc"> — {member.description}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {structure.commander && (
        <div className="co-tree-branch">
          <div className="co-tree-label co-tree-label-nested">Воевода</div>
          <div className="co-tree-content co-tree-content-nested">
            <div className="co-tree-member" onClick={() => handleAnalyze(structure.commander!.nick)}>
              <span className="co-member-icon">⚔️</span>
              <span className="co-member-nick">{structure.commander!.nick}</span>
              {structure.commander!.description && (
                <span className="co-member-desc"> — {structure.commander!.description}</span>
              )}
            </div>
          </div>
        </div>
      )}

      {structure.has_members && (
        <div className="co-tree-branch">
          <div className="co-tree-label co-tree-label-nested">Члены клана</div>
          <div className="co-tree-content co-tree-content-nested">
            <div className="co-tree-member co-tree-link" onClick={goToMembers}>
              <span className="co-member-icon">📋</span>
              <span className="co-member-nick">Список всех участников</span>
              <span className="co-member-count">({info.current_players})</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="clan-overview">
      <div className="co-hero">
        <div className="co-logo-container">
          {info.logo_big ? (
            <img className="co-logo" src={info.logo_big} alt={info.name} />
          ) : (
            <div className="co-logo-placeholder">🏰</div>
          )}
        </div>
        <div className="co-hero-content">
          <h1 className="co-name">{info.name}</h1>
        </div>
      </div>

      <div className="co-stats-grid">
        <div className="co-stat-card">
          <div className="co-stat-icon">📊</div>
          <div className="co-stat-value">{info.clan_level}</div>
          <div className="co-stat-label">Уровень клана</div>
        </div>
        <div className="co-stat-card">
          <div className="co-stat-icon">🏛️</div>
          <div className="co-stat-value">{info.step}</div>
          <div className="co-stat-label">Ступень</div>
        </div>
        <div className="co-stat-card co-stat-talents">
          <div className="co-stat-icon">✨</div>
          <div className="co-stat-value">{info.talents}</div>
          <div className="co-stat-label">Таланты</div>
        </div>
        <div className="co-stat-card co-stat-rank">
          <div className="co-stat-icon">👑</div>
          <div className="co-stat-value co-stat-text">{info.clan_rank || '—'}</div>
          <div className="co-stat-label">Звание</div>
        </div>
      </div>

      {info.structure_warning && (
        <div className="co-structure-warning">
          ⚠️ {info.structure_warning}
        </div>
      )}

      <div className="co-history-section">
        <button 
          className="co-history-toggle"
          onClick={() => setHistoryExpanded(!historyExpanded)}
        >
          <span className="co-history-title">📜 История клана</span>
          <span className="co-history-arrow">{historyExpanded ? '▲' : '▼'}</span>
        </button>
        <div className={`co-history-content ${historyExpanded ? 'expanded' : ''}`}>
          <p className="co-history-text">
            {historyExpanded ? CLAN_HISTORY : historyPreview}
            {!historyExpanded && '…'}
          </p>
        </div>
      </div>

      <div className="co-players-section">
        <h3 className="co-section-title">Состав клана</h3>
        <div className="co-players-card">
          <div className="co-players-display">
            <div className="co-players-numbers">
              <span className="co-players-current">{info.current_players}</span>
              <span className="co-players-separator">/</span>
              <span className="co-players-total">{info.total_players}</span>
            </div>
            <div className="co-players-label">игроков</div>
          </div>
          <div className="co-players-gauge">
            <div className="co-gauge-track">
              <div 
                className="co-gauge-fill" 
                style={{ width: `${playerPercent}%` }}
              />
            </div>
            <div className="co-gauge-labels">
              <span>0</span>
              <span className="co-gauge-percent">{playerPercent}%</span>
              <span>{info.total_players}</span>
            </div>
          </div>
          <div className="co-players-empty">
            Свободно: {info.total_players - info.current_players} мест
          </div>
        </div>
      </div>

      <div className="co-structure-section">
        <div className="co-structure-header">
          <h3 className="co-section-title">Структура клана</h3>
          {!editingStructure && (
            <button className="co-edit-btn" onClick={() => setEditingStructure(true)}>
              ✏️ Редактировать
            </button>
          )}
        </div>
        {editingStructure ? renderStructureEdit() : renderStructureView()}
      </div>
    </div>
  );
}
