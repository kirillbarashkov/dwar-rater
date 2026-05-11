import apiClient from './client';

export interface ExportRequest {
  format: 'html' | 'markdown' | 'pdf';
  sections: string[];
  snapshot_id?: number;
  data?: Record<string, unknown>;
}

export async function exportCharacter(request: ExportRequest): Promise<Blob> {
  const response = await apiClient.post('/api/export/character', request, {
    responseType: 'blob',
  });
  return response.data;
}

export const EXPORT_SECTIONS = [
  { key: 'identity', label: 'Идентификация' },
  { key: 'combat_stats', label: 'Боевая статистика' },
  { key: 'characteristics', label: 'Характеристики' },
  { key: 'equipment', label: 'Экипировка' },
  { key: 'effects', label: 'Эффекты' },
  { key: 'medals', label: 'Медали' },
  { key: 'records', label: 'Рекорды' },
  { key: 'professions', label: 'Профессии' },
  { key: 'additional', label: 'Дополнительно' },
] as const;

export const EXPORT_FORMATS = [
  { key: 'html', label: 'HTML' },
  { key: 'markdown', label: 'Markdown' },
  { key: 'pdf', label: 'PDF' },
] as const;
