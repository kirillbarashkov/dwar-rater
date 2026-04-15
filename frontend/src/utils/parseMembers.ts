import type { ClanMemberData, ClanStructure } from '../types/clanInfo';

export interface ClanInfoData {
  name?: string;
  logo_big?: string;
  logo_small?: string;
  clan_rank?: string;
  clan_level?: number;
  step?: number;
  talents?: number;
  total_players?: number;
  current_players?: number;
  clan_structure?: ClanStructure;
}

export interface ParseResult {
  members: Partial<ClanMemberData>[];
  clanInfo?: ClanInfoData;
  errors: string[];
}

interface RawMember {
  nick?: string;
  name?: string;
  level?: number | string;
  clan_role?: string;
  role?: string;
  game_rank?: string;
  rank?: string;
  profession?: string;
  prof?: string;
  profession_level?: number | string;
  prof_level?: number | string;
  icon?: string;
  emoji?: string;
  join_date?: string;
  date_joined?: string;
  trial_until?: string;
  trial?: string;
}

const DEFAULT_CLAN_ROLE = 'Рыцарь Ордена';

function parseClanInfo(content: string): ClanInfoData | undefined {
  const lines = content.split(/\r?\n/);
  const result: ClanInfoData = {};
  let inStructure = false;
  let structureText = '';

  for (const line of lines) {
    const trimmed = line.trim();
    
    if (trimmed.startsWith('## Лого')) continue;
    if (trimmed.startsWith('## Характеристики')) continue;
    if (trimmed.startsWith('## Количество игроков')) continue;
    if (trimmed.startsWith('## Члены клана')) break;
    
    if (trimmed.startsWith('## Структура клана')) {
      inStructure = true;
      continue;
    }
    
    if (trimmed.startsWith('#')) continue;
    
    if (inStructure) {
      structureText += trimmed + '\n';
    }
    
    if (trimmed.startsWith('- Лого (big):')) {
      result.logo_big = trimmed.replace('- Лого (big):', '').trim();
    }
    
    const levelMatch = trimmed.match(/^- Уровень клана:\s*(\d+)/);
    if (levelMatch) {
      result.clan_level = parseInt(levelMatch[1], 10);
    }
    
    const stepMatch = trimmed.match(/^- Ступень клана:\s*(\d+)/);
    if (stepMatch) {
      result.step = parseInt(stepMatch[1], 10);
    }
    
    const talentsMatch = trimmed.match(/^- Развитие талантов клана:\s*(\d+)/);
    if (talentsMatch) {
      result.talents = parseInt(talentsMatch[1], 10);
    }
    
    const rankMatch = trimmed.match(/^- Звание клана:\s*(.+)/);
    if (rankMatch) {
      result.clan_rank = rankMatch[1].trim();
    }
    
    if (trimmed.includes('Всего доступно:')) {
      const totalMatch = trimmed.match(/Всего доступно:\s*(\d+)/);
      if (totalMatch) result.total_players = parseInt(totalMatch[1], 10);
    }
    
    if (trimmed.includes('Текущее:')) {
      const currentMatch = trimmed.match(/Текущее:\s*(\d+)/);
      if (currentMatch) result.current_players = parseInt(currentMatch[1], 10);
    }
  }
  
  if (structureText) {
    result.clan_structure = parseClanStructure(structureText);
  }
  
  return Object.keys(result).length > 0 ? result : undefined;
}

function parseClanStructure(text: string): ClanStructure | undefined {
  const structure: ClanStructure = {
    leader: undefined,
    deputies: [],
    council: [],
    commander: undefined,
    has_members: true
  };
  
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  
  let pendingSection = '';
  
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed || trimmed.startsWith('```')) continue;
    
    if (trimmed.startsWith('Глава клана') || trimmed.startsWith('Лидер')) {
      pendingSection = 'leader';
      continue;
    }
    
    if (trimmed.includes('Зам.главы') || trimmed.includes('Зам. Главы')) {
      pendingSection = 'deputy';
      continue;
    }
    
    if (trimmed.includes('Совет клана')) {
      pendingSection = 'council';
      continue;
    }
    
    if (trimmed.includes('Воевода')) {
      pendingSection = 'commander';
      continue;
    }
    
    if (trimmed.includes('Члены клана')) {
      pendingSection = 'members';
      continue;
    }
    
    const memberMatch = trimmed.match(/^[├│└─┬┼─\s]+([^:]+?)\s*:\s*(.+)/);
    if (memberMatch) {
      let name = memberMatch[1].trim();
      if (name.endsWith('-')) {
        name = name.slice(0, -1);
      }
      const desc = memberMatch[2].trim();
      
      if (structure.leader === undefined) {
        structure.leader = { nick: name, description: desc };
      } else if (pendingSection === 'deputy' || (pendingSection === 'leader' && name !== '-Витчер-')) {
        structure.deputies?.push({ nick: name, description: desc });
      } else if (pendingSection === 'council') {
        structure.council?.push({ nick: name, description: desc });
      } else if (pendingSection === 'commander') {
        structure.commander = { nick: name, description: desc };
      }
    }
    
    if (trimmed.startsWith('Глава клана') || trimmed.startsWith('Лидер')) {
      pendingSection = 'leader';
    } else if (!trimmed.includes(':') && !trimmed.match(/^[├│└─┬┼]/)) {
      if (trimmed !== 'Глава клана' && trimmed !== 'Лидер') {
        pendingSection = '';
      }
    }
  }
  
  return structure;
}

const CLAN_ROLES = [
  'Глава Ордена', 'Зам. Главы', 'Совесть', 'Рыцарь Ордена', 'Леди Ордена',
  'ГардеМаринкА', 'Фея на метле', 'Лентяй', 'Пельмешка', 'Dead\'ok',
  'Воевода', '9-ть жЫзней)', 'УлитЫчка)', 'РудольФ', 'Сосиска',
];

function normalizeLevel(level: number | string | undefined): number {
  if (!level) return 1;
  const parsed = typeof level === 'string' ? parseInt(level, 10) : level;
  return isNaN(parsed) ? 1 : Math.max(1, parsed);
}

function normalizeString(value: unknown): string {
  if (typeof value === 'string') return value.trim();
  if (typeof value === 'number') return String(value);
  return '';
}

function extractLevel(text: string): number {
  const match = text.match(/\[(\d+)\]/);
  return match ? parseInt(match[1], 10) : 1;
}

function findClanRole(text: string): string {
  const upperText = text.toLowerCase();
  for (const role of CLAN_ROLES) {
    if (upperText.includes(role.toLowerCase())) {
      return role;
    }
  }
  return '';
}

function findProfession(text: string): { profession: string; level: number } {
  const match = text.match(/^(Палач|Целитель|Взломщик):\s*(\d+)/);
  if (match) {
    return { profession: match[1], level: parseInt(match[2], 10) };
  }
  return { profession: '', level: 0 };
}

function parseMarkdownTableLine(line: string): string[] {
  return line.split('|').map(s => s.trim()).filter(s => s && !s.match(/^[-:]+$/));
}

function parseMarkdownTable(content: string): ParseResult {
  const lines = content.split(/\r?\n/);
  const errors: string[] = [];
  const members: Partial<ClanMemberData>[] = [];

  let headerFound = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (!line.startsWith('|')) continue;

    if (!headerFound) {
      if (line.includes('Боевое звание') || line.includes('Ник')) {
        headerFound = true;
      }
      continue;
    }

    if (line.match(/^[|\s-]+$/)) continue;

    const parts = parseMarkdownTableLine(line);

    if (parts.length < 2) continue;

    const game_rank = parts[0];

    let nick: string;
    let level: number;

    if (parts.length === 5) {
      nick = parts[1];
      level = extractLevel(parts[2]);

      let profession = '';
      let profession_level = 0;
      let clan_role = DEFAULT_CLAN_ROLE;

      const fourth = parts[3];
      if (fourth && fourth !== '-') {
        const profResult = findProfession(fourth);
        if (profResult.profession) {
          profession = profResult.profession;
          profession_level = profResult.level;
        } else {
          const foundRole = findClanRole(fourth);
          if (foundRole) clan_role = foundRole;
        }
      }

      if (parts[4]) {
        const foundRole = findClanRole(parts[4]);
        if (foundRole) clan_role = foundRole;
      }

      if (!nick) {
        errors.push(`Строка ${i + 1}: пустой ник`);
        continue;
      }

      members.push({
        nick, level, game_rank, profession, profession_level, clan_role,
        icon: '', join_date: '', trial_until: '',
      });

    } else if (parts.length === 4) {
      const levelMatch = parts[1].match(/^(.+?)\s*\[(\d+)\]$/);

      if (levelMatch) {
        nick = levelMatch[1];
        level = parseInt(levelMatch[2], 10);
      } else {
        nick = parts[1];
        level = extractLevel(parts[2]);
      }

      let profession = '';
      let profession_level = 0;
      let clan_role = DEFAULT_CLAN_ROLE;

      const third = parts.length >= 3 ? parts[2] : '';
      const fourth = parts.length >= 4 ? parts[3] : '';

      const profResult = findProfession(third);
      if (profResult.profession) {
        profession = profResult.profession;
        profession_level = profResult.level;
        if (fourth) {
          const foundRole = findClanRole(fourth);
          if (foundRole) clan_role = foundRole;
        }
      } else {
        const foundRole = findClanRole(third);
        if (foundRole) {
          clan_role = foundRole;
        } else if (fourth) {
          const foundRole2 = findClanRole(fourth);
          if (foundRole2) clan_role = foundRole2;
        }
      }

      if (!nick) {
        errors.push(`Строка ${i + 1}: пустой ник`);
        continue;
      }

      members.push({
        nick, level, game_rank, profession, profession_level, clan_role,
        icon: '', join_date: '', trial_until: '',
      });

    } else if (parts.length === 3) {
      const levelMatch = parts[1].match(/^(.+?)\s*\[(\d+)\]$/);

      if (levelMatch) {
        nick = levelMatch[1];
        level = parseInt(levelMatch[2], 10);
      } else {
        nick = parts[1];
        level = 1;
      }

      const clan_role = findClanRole(parts[2]) || DEFAULT_CLAN_ROLE;

      if (!nick) {
        errors.push(`Строка ${i + 1}: пустой ник`);
        continue;
      }

      members.push({
        nick, level, game_rank, profession: '', profession_level: 0, clan_role,
        icon: '', join_date: '', trial_until: '',
      });

    } else {
      nick = parts[1];
      level = extractLevel(parts[1]);

      if (!nick) {
        errors.push(`Строка ${i + 1}: пустой ник`);
        continue;
      }

      members.push({
        nick, level, game_rank, profession: '', profession_level: 0, clan_role: DEFAULT_CLAN_ROLE,
        icon: '', join_date: '', trial_until: '',
      });
    }
  }

  return { members, errors };
}

function parseCSVLine(line: string, delimiter: string = '\t'): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === delimiter && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }

  result.push(current.trim());
  return result;
}

function parseJSONContent(content: string): ParseResult {
  const errors: string[] = [];

  try {
    const data = JSON.parse(content);

    if (Array.isArray(data)) {
      const members = data.map((item, index) => {
        if (typeof item !== 'object' || item === null) {
          errors.push(`Строка ${index + 1}: неверный формат объекта`);
          return null;
        }
        const raw = item as RawMember;
        const nick = normalizeString(raw.nick || raw.name);
        if (!nick) {
          errors.push(`Строка ${index + 1}: отсутствует ник`);
          return null;
        }
        return {
          nick,
          level: normalizeLevel(raw.level),
          clan_role: normalizeString(raw.clan_role || raw.role) || DEFAULT_CLAN_ROLE,
          game_rank: normalizeString(raw.game_rank || raw.rank),
          profession: normalizeString(raw.profession || raw.prof),
          profession_level: normalizeLevel(raw.profession_level || raw.prof_level),
          icon: normalizeString(raw.icon || raw.emoji),
          join_date: normalizeString(raw.join_date || raw.date_joined),
          trial_until: normalizeString(raw.trial_until || raw.trial),
        };
      }).filter((m) => m !== null) as Partial<ClanMemberData>[];

      return { members, errors };
    }

    if (typeof data === 'object' && data !== null) {
      if ('members' in data && Array.isArray(data.members)) {
        const result = parseJSONContent(JSON.stringify(data.members));
        return { members: result.members, errors: result.errors };
      }
      if ('data' in data && Array.isArray(data.data)) {
        const result = parseJSONContent(JSON.stringify(data.data));
        return { members: result.members, errors: result.errors };
      }
    }

    errors.push('JSON не содержит массив участников');
    return { members: [], errors };
  } catch (e) {
    errors.push(`Ошибка парсинга JSON: ${e}`);
    return { members: [], errors };
  }
}

function parseCSVContent(content: string, delimiter: string = '\t'): ParseResult {
  const lines = content.split(/\r?\n/).filter(line => line.trim());
  const errors: string[] = [];

  if (lines.length === 0) {
    errors.push('Пустой файл');
    return { members: [], errors };
  }

  const headerLine = lines[0];
  const headers = parseCSVLine(headerLine, delimiter).map(h => h.toLowerCase());

  const nickIndex = headers.findIndex(h => ['nick', 'ник', 'name', 'имя', 'персонаж'].includes(h));
  const levelIndex = headers.findIndex(h => ['level', 'уровень', 'ур', 'lvl', 'лвл'].includes(h));
  const roleIndex = headers.findIndex(h => ['role', 'clan_role', 'звание', 'должность', 'клановое'].includes(h));
  const rankIndex = headers.findIndex(h => ['rank', 'ранг', 'game_rank', 'статус'].includes(h));
  const profIndex = headers.findIndex(h => ['profession', 'профессия', 'prof'].includes(h));
  const profLevelIndex = headers.findIndex(h => ['profession_level', 'prof_level', 'урпроф', 'профа'].includes(h));
  const iconIndex = headers.findIndex(h => ['icon', 'иконка', 'emoji'].includes(h));
  const joinDateIndex = headers.findIndex(h => ['join_date', 'joined', 'вступил', 'дата'].includes(h));
  const trialIndex = headers.findIndex(h => ['trial', 'trial_until', 'испытательный', 'испыт'].includes(h));

  if (nickIndex === -1) {
    errors.push('Не найдена колонка с ником (nick, ник, name)');
    return { members: [], errors };
  }

  const members: Partial<ClanMemberData>[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i], delimiter);

    if (values.length === 0 || (values.length === 1 && !values[0])) continue;

    const nick = normalizeString(values[nickIndex]);
    if (!nick) {
      errors.push(`Строка ${i + 1}: пустой ник`);
      continue;
    }

    members.push({
      nick,
      level: normalizeLevel(levelIndex >= 0 ? values[levelIndex] : undefined),
      clan_role: roleIndex >= 0 ? normalizeString(values[roleIndex]) : DEFAULT_CLAN_ROLE,
      game_rank: rankIndex >= 0 ? normalizeString(values[rankIndex]) : '',
      profession: profIndex >= 0 ? normalizeString(values[profIndex]) : '',
      profession_level: profLevelIndex >= 0 ? normalizeLevel(values[profLevelIndex]) : 0,
      icon: iconIndex >= 0 ? normalizeString(values[iconIndex]) : '',
      join_date: joinDateIndex >= 0 ? normalizeString(values[joinDateIndex]) : '',
      trial_until: trialIndex >= 0 ? normalizeString(values[trialIndex]) : '',
    });
  }

  return { members, errors };
}

function parseTextContent(content: string): ParseResult {
  const lines = content.split(/\r?\n/).filter(line => line.trim());
  const errors: string[] = [];
  const members: Partial<ClanMemberData>[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (!line) continue;

    const parts = line.split(/[\t,;|]+/).map(p => p.trim()).filter(p => p);

    if (parts.length === 0) continue;

    const nick = parts[0];

    if (!nick) {
      errors.push(`Строка ${i + 1}: пустой ник`);
      continue;
    }

    const level = parts.length > 1 ? normalizeLevel(parts[1]) : 1;
    const clan_role = parts.length > 2 ? parts[2] : DEFAULT_CLAN_ROLE;

    members.push({
      nick,
      level,
      clan_role,
      game_rank: '',
      profession: '',
      profession_level: 0,
      icon: '',
      join_date: '',
      trial_until: '',
    });
  }

  return { members, errors };
}

export function parseMembersFile(content: string): ParseResult {
  const trimmed = content.trim();

  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    return parseJSONContent(trimmed);
  }

  const firstLine = trimmed.split(/\r?\n/)[0];

  if (trimmed.startsWith('#')) {
    const clanInfo = parseClanInfo(trimmed);
    
    const codeBlockMatch = trimmed.match(/```[\s\S]*?\|[\s\S]*?\|[\s\S]*?```/);
    if (codeBlockMatch) {
      const tableContent = codeBlockMatch[0].replace(/```\w*\n?/g, '').trim();
      const result = parseMarkdownTable(tableContent);
      return { ...result, clanInfo };
    }
    
    const directTableMatch = trimmed.match(/\|[\s\S]*?\|[\s\S]*?\n\|[\s|-]+[\s\S]*?\|[\s\S]*?(?=```|$)/);
    if (directTableMatch) {
      const result = parseMarkdownTable(directTableMatch[0]);
      return { ...result, clanInfo };
    }
    
    return { members: [], errors: ['Не найдена таблица участников в markdown файле'], clanInfo };
  }

  const hasMarkdownTable = firstLine.includes('|') && firstLine.includes('Боевое звание');

  if (hasMarkdownTable || (firstLine.includes('|') && trimmed.includes('---'))) {
    const result = parseMarkdownTable(trimmed);
    const clanInfo = parseClanInfo(trimmed);
    return { ...result, clanInfo };
  }

  const hasTabDelimiter = firstLine.includes('\t');

  if (hasTabDelimiter || firstLine.split(/[\t,]/).length > 3) {
    return parseCSVContent(trimmed, hasTabDelimiter ? '\t' : ',');
  }

  return parseTextContent(trimmed);
}
