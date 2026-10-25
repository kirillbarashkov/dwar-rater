FROM python:3.14-slim

# Build metadata — injected by CI (docker compose build --build-arg ...).
# Fallbacks keep local `docker compose build` working without args.
ARG APP_VERSION=dev
ARG APP_GIT_HASH=unknown
ARG APP_BRANCH=unknown
ARG APP_BUILD_DATE=unknown

WORKDIR /app

# System dependencies for WeasyPrint (PDF generation) and PostgreSQL client (pg_dump)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV APP_VERSION=${APP_VERSION} \
    APP_GIT_HASH=${APP_GIT_HASH} \
    APP_BRANCH=${APP_BRANCH} \
    APP_BUILD_DATE=${APP_BUILD_DATE}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Release notes (optional file: absent in local builds — handled at runtime)
COPY RELEASE_NOTES.md* ./

COPY . .
RUN chmod +x entrypoint.sh

# A62: процесс не должен быть root. Бэкенд запускает pg_dump/pg_restore/psql
# через subprocess, и под root любая их ошибка (или компрометация приложения)
# даёт root внутри контейнера, а с монтированными томами — доступ к данным и
# бэкапам. UID фиксированный, чтобы права на томах были предсказуемы.
RUN groupadd -g 10001 app \
    && useradd -u 10001 -g app -m -s /usr/sbin/nologin app \
    && chown -R app:app /app \
    # A39: /backups — общий том с контейнером postgres (там группа postgres = gid 70).
    # Обе стороны должны писать в один каталог, поэтому заводим ту же группу и
    # вешаем setgid: новые файлы наследуют группу, а не только создатель.
    && (groupadd -g 70 dbbackups 2>/dev/null || groupadd -o -g 70 dbbackups) \
    && usermod -aG dbbackups app \
    && mkdir -p /backups \
    && chown 10001:70 /backups \
    && chmod 2775 /backups

USER app

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
