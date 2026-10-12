import { useEffect, useRef, useState } from 'react';
import './ApiDocsTab.css';

/**
 * Вкладка «API (Swagger)» в админке.
 *
 * Swagger UI грузится с unpkg по требованию: CSP приложения (security.py) уже
 * разрешает script-src и style-src с unpkg, поэтому новые зависимости в сборку
 * не добавляются. Спецификация отдаётся бэкендом по /api/openapi.yaml — этот путь
 * в списке исключений авторизации, так что UI забирает её без токена.
 */
const SWAGGER_VERSION = '5.17.14';
const CSS_URL = `https://unpkg.com/swagger-ui-dist@${SWAGGER_VERSION}/swagger-ui.css`;
const JS_URL = `https://unpkg.com/swagger-ui-dist@${SWAGGER_VERSION}/swagger-ui-bundle.js`;
const SPEC_URL = '/api/openapi.yaml';

type SwaggerWindow = Window & {
  SwaggerUIBundle?: (options: Record<string, unknown>) => void;
};

export function ApiDocsTab() {
  const containerRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    // Строгий режим вызывает эффект дважды: без флага скрипт подключался бы дважды.
    if (startedRef.current) return;
    startedRef.current = true;

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = CSS_URL;
    document.head.appendChild(link);

    const script = document.createElement('script');
    script.src = JS_URL;
    script.async = true;
    script.onload = () => {
      const swagger = (window as SwaggerWindow).SwaggerUIBundle;
      if (!swagger || !containerRef.current) {
        setFailed(true);
        return;
      }
      swagger({
        url: SPEC_URL,
        domNode: containerRef.current,
        deepLinking: true,
        docExpansion: 'list',
        defaultModelsExpandDepth: 0,
        tryItOutEnabled: false,
      });
    };
    script.onerror = () => setFailed(true);
    document.body.appendChild(script);

    return () => {
      // Скрипт и стиль остаются в документе: повторное подключение при возврате
      // на вкладку дороже, чем один лишний тег.
    };
  }, []);

  return (
    <div className="api-docs-tab">
      <div className="api-docs-header">
        <h2 className="api-docs-title">API приложения</h2>
        <p className="api-docs-note">
          Спецификация OpenAPI: все эндпоинты, параметры и коды ответов. Отправка
          запросов из интерфейса отключена — раздел только для чтения.
        </p>
      </div>

      {failed && (
        <div className="api-docs-error">
          <p>
            Не удалось загрузить Swagger UI с unpkg.com. Проверьте доступ к внешней
            сети — сама спецификация при этом доступна:{' '}
            <a href={SPEC_URL} target="_blank" rel="noreferrer">
              {SPEC_URL}
            </a>
          </p>
        </div>
      )}

      <div ref={containerRef} className="api-docs-container" />
    </div>
  );
}
