export interface Snapshot {
  id: number;
  nick: string;
  name: string;
  race: string;
  rank: string;
  clan: string;
  snapshot_name: string;
  analyzed_at: string;
}

export interface SnapshotListResponse {
  total: number;
  page: number;
  pages: number;
  snapshots: Snapshot[];
}

export interface SaveSnapshotRequest {
  snapshot_data: Record<string, unknown>;
  snapshot_name: string;
  url: string;
}

export interface SaveSnapshotResponse {
  status: string;
  snapshot_id: number;
  analyzed_at: string;
}
