FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN uv sync --no-dev

ENV DATABASE_URL=${DATABASE_URL:-sqlite:///./calendar.db}
ENV SECRET_KEY=${SECRET_KEY:-dev-change-me-in-production-needs-32-bytes}

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
