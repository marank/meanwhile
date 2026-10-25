# syntax=docker/dockerfile:1
# Production image: nginx serves the frontend and passes the backend's paths on to uvicorn;
# supervisord (PID 1) runs nginx, uvicorn and the task queue's worker. Built for a read-only root
# filesystem (compose.yml): everything runs as "app" and writes only to /tmp and /data.

# --- Frontend ---------------------------------------------------------------------------------
FROM node:24-alpine AS frontend

RUN npm install -g pnpm@10.34.5

WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build-only

# --- App --------------------------------------------------------------------------------------
FROM python:3.14-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/tmp \
    DATA_DIR=/data

RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx gettext-base \
 && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled /etc/nginx/conf.d \
 # supervisord lives outside the app's venv; it's infrastructure, not an app dependency.
 && pip install --no-cache-dir --root-user-action=ignore supervisor \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app \
 && mkdir -p /data && chown app:app /data

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
# The app's own modules too: the root filesystem is read-only at runtime.
RUN python -m compileall -q config core \
 # collectstatic needs settings to import; a throwaway key and password are enough at build time.
 && SECRET_KEY="build-only-$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')" DB_PASSWORD=unused \
    python manage.py collectstatic --noinput

COPY --from=frontend /frontend/dist /srv/spa
COPY docker/nginx.conf docker/django_proxy.conf docker/security_headers.conf /etc/nginx/
COPY docker/app.conf.template /etc/nginx/app.conf.template
COPY docker/supervisord.conf /etc/supervisord.conf
COPY docker/entrypoint.sh docker/start-nginx docker/exit-on-fatal docker/healthcheck /usr/local/bin/

# Everything above is owned by root and read-only for "app"; only /data and /tmp are written.
USER app
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD ["python", "/usr/local/bin/healthcheck"]
ENTRYPOINT ["sh", "/usr/local/bin/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
