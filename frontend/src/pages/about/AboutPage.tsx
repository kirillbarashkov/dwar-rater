import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchAbout } from '../../api/about';
import { Markdown } from '../../components/ui/Markdown';
import type { AboutPayload } from '../../types/about';
import './AboutPage.css';

/**
 * «О проекте» — отдельная страница с внутренними табами.
 *
 * Четыре таба задаёт бэкенд (порядок и подписи — там же, в features/about):
 * описание и цели, что нового, релиз, техдолг. Тексты приезжают markdown-файлами
 * вместе с релизом, поэтому здесь ничего не хардкодится, кроме подписи пустого
 * документа.
 *
 * Доступна любому вошедшему и НЕ заперта воротами привязки персонажа: это рассказ
 * о проекте, а не рабочий инструмент.
 */

function formatUpdated(value: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function AboutPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<AboutPayload | null>(null);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(
    () => new URLSearchParams(window.location.search).get('tab') ?? 'description',
  );

  useEffect(() => {
    let alive = true;
    fetchAbout()
      .then((payload) => {
        if (alive) setData(payload);
      })
      .catch(() => {
        if (alive) setError('Не удалось загрузить материалы о проекте.');
      });
    return () => {
      alive = false;
    };
  }, []);

  // Вкладка живёт в адресе: ссылку на «Что нового» можно переслать, а F5 остаётся
  // на том же табе (тот же приём, что в админке).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set('tab', activeTab);
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
  }, [activeTab]);

  const documents = data?.documents ?? [];
  const currentDocument =
    documents.find((doc) => doc.key === activeTab) ?? documents[0] ?? null;

  return (
    <div className="about-page">
      <div className="about-header">
        <button className="btn btn-ghost about-back-btn" onClick={() => navigate('/')}>
          ← Назад
        </button>
        <h1 className="about-title">О проекте</h1>
        {data && (
          <span
            className="about-version"
            title={`${data.release.build_date} · ${data.release.git_hash} · ${data.release.branch}`}
          >
            v{data.release.version}
          </span>
        )}
      </div>

      {error && <div className="about-error">{error}</div>}

      {!data && !error && <div className="about-loading">Загружаю материалы…</div>}

      {data && (
        <>
          <div className="about-tabs">
            {documents.map((doc) => (
              <button
                key={doc.key}
                className={`about-tab ${currentDocument?.key === doc.key ? 'active' : ''}`}
                onClick={() => setActiveTab(doc.key)}
              >
                {doc.title}
              </button>
            ))}
          </div>

          {currentDocument && (
            <div className="about-content">
              <div className="about-doc-meta">
                {currentDocument.updated && (
                  <span>Обновлено: {formatUpdated(currentDocument.updated)}</span>
                )}
                <span className="about-doc-file">{currentDocument.file}</span>
              </div>

              {/* «Релиз»: сверху — то, что реально записано в git (сжато), ниже —
                  подробный разбор релизов. Так видно разницу между записью в
                  истории и рассказом для человека. */}
              {currentDocument.key === 'releases' && data.release.notes.trim() && (
                <section className="about-release-now">
                  <h2 className="about-release-now-title">
                    Текущий релиз v{data.release.version} — как он записан в git
                  </h2>
                  <Markdown text={data.release.notes} />
                </section>
              )}

              {currentDocument.markdown.trim() ? (
                <Markdown text={currentDocument.markdown} />
              ) : (
                <div className="about-empty">
                  Документ ещё не написан: файла <code>{currentDocument.file}</code> нет в сборке.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
