export interface ClosedProfileData {
  id: number;
  nick: string;
  first_seen_closed: string;
  last_checked: string | null;
  check_count: number;
  status: 'closed' | 'opened';
  level: string | null;
  rank: string | null;
  clan: string | null;
  snapshot_id: number | null;
  notes: string | null;
  is_scanned_open: boolean;
  scanned_open_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CheckResult {
  status: 'opened' | 'closed' | 'error';
  data?: Record<string, unknown>;
  profile: ClosedProfileData;
  error?: string;
}

export interface BatchScanResult {
  results: Array<{
    nick: string;
    status: 'opened' | 'closed' | 'error' | 'not_found';
    data?: Record<string, unknown>;
  }>;
}
