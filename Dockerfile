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

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default \
    && useradd --system --no-create-home app

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
# Django admin's static files, served by nginx.
RUN python manage.py collectstatic --no-input

COPY --from=frontend /frontend/dist /srv/frontend
COPY docker/nginx.conf /etc/nginx/conf.d/app.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/app.conf
COPY docker/entrypoint.sh docker/trusted-proxies.sh /usr/local/bin/

EXPOSE 80

ENTRYPOINT ["entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
