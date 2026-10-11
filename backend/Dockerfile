FROM ghcr.io/astral-sh/uv:python3.12-bookworm

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libxml2-dev libxslt1-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# ASGI: the app, the API, CalDAV and the WebSocket for live updates. Behind a reverse proxy that
# terminates HTTPS; --proxy-headers takes the client's scheme and address from it.
# Several workers need REDIS_URL, so that live updates reach every worker's WebSockets.
CMD ["sh", "-c", "exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers ${WEB_WORKERS:-4} --lifespan off --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-*}\" --ws-ping-interval 20 --ws-ping-timeout 20 --ws-max-size 65536"]
