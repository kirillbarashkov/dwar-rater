export interface Clan {
  id: number;
  name: string;
  created_at: string;
}

export interface ClanMember {
  user_id: number;
  username: string;
  role: 'leader' | 'officer' | 'member';
  joined_at: string;
}

export interface ChatRoom {
  id: number;
  name: string;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  user_id: number;
  username: string;
  content: string;
  created_at: string;
  is_deleted: boolean;
}

// A45: канон сортировки для аналитики казны и талантов.
export type SortDirection = 'asc' | 'desc';

export interface SortConfig {
  column: string | null;
  direction: SortDirection;
}
