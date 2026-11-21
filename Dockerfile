# syntax=docker/dockerfile:1
# Production image, one for two containers (compose.yml):
#   app     supervisord (PID 1) runs nginx (frontend, proxy) and uvicorn (API, CalDAV, WebSockets)
#   worker  `docker/worker`: the task queue's worker (emails, reminders, iMIP, nightly backups)
# Built for a read-only root filesystem: everything runs as "app" and writes only to /tmp, /data
# and (worker) /backups.

# Versions in one place. Images are pinned by tag and digest (of the multi-platform index, so the
# amd64 and arm64 builds use the same pin); Dependabot updates both. Dependabot does not see the
# ARGs: PG_MAJOR follows the postgres image of compose.yml, SUPERVISOR_VERSION is bumped by hand.
ARG PG_MAJOR=18
ARG SUPERVISOR_VERSION=4.3.0

# --- Frontend ---------------------------------------------------------------------------------
FROM node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5 AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
# pnpm in the version of packageManager in package.json (the one place it is set).
RUN npm install -g "$(node -p "require('./package.json').packageManager.split('+')[0]")" \
 && pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build-only

# --- uv ---------------------------------------------------------------------------------------
# Only mounted while the venv is built; the final image has no package installer for the app.
FROM ghcr.io/astral-sh/uv:0.13@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv

# --- App --------------------------------------------------------------------------------------
# Named "runtime": CI builds it without cache (no-cache-filters), so system package updates are
# never held back.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS runtime
ARG PG_MAJOR
ARG SUPERVISOR_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/tmp \
    DATA_DIR=/data \
    BACKUP_DIR=/backups

# nginx; gettext-base for envsubst (start-nginx), gettext for compilemessages; postgresql-client
# from PostgreSQL's own repository in the server's major, so pg_dump (nightly backups) accepts the
# server. curl only for the key and removed again. supervisord lives outside the app's venv: it's
# infrastructure, not an app dependency. pip is not needed at runtime, so it goes afterwards.
# No setuid/setgid programs (su, passwd, mount, ...): nothing in the container may gain rights.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends nginx gettext-base gettext curl ca-certificates \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/keyrings/pgdg.asc \
 && echo "deb [signed-by=/usr/share/keyrings/pgdg.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends "postgresql-client-${PG_MAJOR}" \
 && apt-get purge -y curl && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled /etc/nginx/conf.d \
 && pip install --no-cache-dir --root-user-action=ignore "supervisor==${SUPERVISOR_VERSION}" \
 && pip uninstall -y --root-user-action=ignore pip \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app \
 && install -d -o app -g app -m 0700 /data /backups \
 && find / -xdev -perm /6000 -type f -exec chmod a-s {} +

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
# uv's download cache stays in a BuildKit cache, outside the image (HOME is /tmp).
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/tmp/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
# The app's own modules too: the root filesystem is read-only at runtime. collectstatic needs
# settings to import; a throwaway key and password are enough at build time.
RUN python -m compileall -q config apps \
 && SECRET_KEY="build-only-$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')" DB_PASSWORD=unused \
    sh -c 'python manage.py collectstatic --noinput && python manage.py compilemessages --ignore=.venv'

COPY --from=frontend /frontend/dist /srv/spa
COPY docker/nginx.conf docker/django_proxy.conf docker/security_headers.conf /etc/nginx/
COPY docker/app.conf.template /etc/nginx/app.conf.template
COPY docker/supervisord.conf /etc/supervisord.conf
COPY docker/entrypoint.sh docker/start-nginx docker/exit-on-fatal docker/healthcheck docker/smoke-test docker/worker /usr/local/bin/

# Everything above is owned by root and read-only for "app"; only /data, /backups and /tmp are written.
USER app
EXPOSE 8080
VOLUME ["/data", "/backups"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD ["python", "/usr/local/bin/healthcheck"]
ENTRYPOINT ["sh", "/usr/local/bin/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
