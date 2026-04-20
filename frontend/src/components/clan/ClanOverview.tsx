import { useState, useEffect } from 'react';
import type { ClanInfoData } from '../../types/clanInfo';
import { getClanInfo } from '../../api/clanInfo';
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
  const [isLoading, setIsLoading] = useState(true);
  const [historyExpanded, setHistoryExpanded] = useState(false);

  useEffect(() => {
    getClanInfo(clanId)
      .then(setInfo)
      .catch(() => setInfo(null))
      .finally(() => setIsLoading(false));
  }, [clanId]);

  if (isLoading) return <LoadingSpinner />;
  if (!info) return <p className="clan-error">Не удалось загрузить информацию о клане</p>;

  const playerPercent = info.total_players > 0 
    ? Math.round((info.current_players / info.total_players) * 100) 
    : 0;

  const handleAnalyze = (nick: string) => {
    const url = `https://w1.dwar.ru/user_info.php?nick=${encodeURIComponent(nick)}`;
    sessionStorage.setItem('pending_analyze', url);
    window.location.href = '/';
  };

  const goToMembers = () => {
    if (onSwitchTab) {
      onSwitchTab('members');
    }
    window.scrollTo(0, 0);
  };

  const structure = info.clan_structure || {};
  
  const historyPreview = CLAN_HISTORY.slice(0, 200);

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
        <h3 className="co-section-title">Структура клана</h3>
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
              <div className="co-tree-label co-tree-label-nested">Зам.главы</div>
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
      </div>
    </div>
  );
}
