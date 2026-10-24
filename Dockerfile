# Production image: nginx serves the frontend and passes the backend's paths on to uvicorn;
# supervisord runs nginx, uvicorn and the task queue's worker. The migrations run on every start
# (docker/entrypoint.sh), before any of them.

# --- Frontend ---------------------------------------------------------------------------------
FROM node:24-alpine AS frontend

RUN npm install -g pnpm@10.28.0

WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# --- App --------------------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Everything runs as "app", nginx included: it listens on 8080 and keeps its pid, temporary files,
# logs and the list of trusted proxies (written on start) where that user may write.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default \
    && useradd --system --no-create-home app \
    && sed -i -e '/^user /d' -e 's|^pid .*|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf \
    && touch /etc/nginx/trusted-proxies.conf \
    && chown -R app /var/lib/nginx /var/log/nginx /etc/nginx/trusted-proxies.conf

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
# Django admin's static files, served by nginx. The settings need a SECRET_KEY outside development;
# collecting files uses none, the real one comes with the container's environment.
RUN SECRET_KEY=collectstatic-only python manage.py collectstatic --no-input

COPY --from=frontend /frontend/dist /srv/frontend
COPY docker/nginx.conf /etc/nginx/conf.d/app.conf
COPY docker/security-headers.conf /etc/nginx/security-headers.conf
COPY docker/supervisord.conf /etc/supervisor/app.conf
COPY docker/entrypoint.sh docker/trusted-proxies.sh /usr/local/bin/

USER app
EXPOSE 8080

ENTRYPOINT ["entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/app.conf"]
