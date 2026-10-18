/** Документы вкладки «О проекте» — то, что отдаёт GET /api/about. */

export interface AboutDocument {
  key: string;
  title: string;
  /** Имя markdown-файла в backend/docs/about/ — показываем в подписи «нет текста». */
  file: string;
  /** Время правки файла у бэкенда; null — файла нет. */
  updated: string | null;
  markdown: string;
}

export interface AboutRelease {
  version: string;
  git_hash: string;
  build_date: string;
  branch: string;
  /** RELEASE_NOTES.md — сжатая запись релиза, которая попадает в git. */
  notes: string;
}

export interface AboutPayload {
  documents: AboutDocument[];
  release: AboutRelease;
}
