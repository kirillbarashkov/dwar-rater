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

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
