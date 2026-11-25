# The project's commands — the one place they live. CI (.github/workflows/build.yaml) and the
# VS Code tasks (.vscode/tasks.json) call these recipes, so a check is changed here and
# nowhere else. `just` lists them. Needs just >= 1.42 (working-directory and parallel attributes).

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# List the recipes
default:
    @just --list

# --- Setup --------------------------------------------------------------------------

# Install all dependencies
setup: setup-backend setup-frontend

[working-directory: 'backend']
setup-backend:
    uv sync

[working-directory: 'frontend']
setup-frontend:
    pnpm install

# --- Development ----------------------------------------------------------------------

# Backend and frontend together → http://localhost:6326; Ctrl+C stops both
[parallel]
dev: dev-backend dev-frontend

# Django on :8000 under uvicorn like production, restarting on changes (SQLite in backend/data,
# jobs in-process, no worker); applies migrations first
[working-directory: 'backend']
dev-backend: migrate
    uv run uvicorn config.asgi:application --reload --port 8000

# Vite on :6326, proxying the backend's paths to Django
[working-directory: 'frontend']
dev-frontend:
    pnpm dev

# Optional PostgreSQL, Redis and Mailpit (compose.dev.yml); then DB_HOST=localhost in .env
services:
    docker compose -f compose.dev.yml up -d postgres redis mailpit

# The task queue's worker, natively; only with PostgreSQL (DB_HOST)
[working-directory: 'backend']
dev-worker:
    uv run python manage.py procrastinate worker

# Apply migrations and set up the admin user of ADMIN_EMAIL
[working-directory: 'backend']
migrate:
    uv run python manage.py migrate
    uv run python manage.py ensure_admin

# After model changes; commit the migrations
[working-directory: 'backend']
migrations:
    uv run python manage.py makemigrations

# After API changes: schema -> frontend/openapi.json -> src/api/schema.d.ts; commit both
[working-directory: 'frontend']
api-types: api-schema
    pnpm api:types

[working-directory: 'backend']
api-schema:
    uv run python manage.py export_openapi_schema --api apps.core.api.api --indent 2 --output ../frontend/openapi.json

# After new backend texts; then translate backend/locale/de/LC_MESSAGES/django.po, and in
# locale/de_Informal the ones that address the reader (the rest falls back to the formal German)
[working-directory: 'backend']
messages:
    uv run python manage.py makemessages -l de -l de_Informal --no-location --ignore=.venv

[working-directory: 'backend']
compile-messages:
    uv run python manage.py compilemessages --ignore=.venv

# Bring .env up to date with .env.example, keeping its values (old one as .env.bak)
[working-directory: 'backend']
sync-env:
    uv run python ../scripts/sync_env.py

# --- Checks (= CI) --------------------------------------------------------------------

# Everything CI checks; must pass before a push
check: check-backend check-deploy check-frontend check-workflows

# ruff, mypy, complexipy, deptry, import layers, licenses, migrations, Django checks, translations, OpenAPI, tests
[working-directory: 'backend']
check-backend:
    uv sync --locked
    uv run ruff check --output-format=concise .
    uv run ruff format --check .
    uv run mypy .
    uv run complexipy --failed apps config
    uv run deptry .
    uv run lint-imports
    uv run python scripts/check_licenses.py
    uv run python manage.py makemigrations --check --dry-run
    uv run python manage.py check --fail-level WARNING
    uv run python manage.py makemessages -l de -l de_Informal --no-location --ignore=.venv
    uv run python scripts/check_translations.py
    uv run python manage.py compilemessages --ignore=.venv
    uv run python scripts/check_openapi.py
    uv run pytest -q --cov -n auto

# Django's deploy checks with production-like settings (deploy-check.env)
[working-directory: 'backend']
check-deploy:
    uv run --env-file deploy-check.env python manage.py check --deploy --fail-level WARNING

# prettier, oxlint, eslint, knip, types, tests, API types, build, bundle size, licenses, audit
[working-directory: 'frontend']
check-frontend:
    pnpm install --frozen-lockfile
    pnpm check
    pnpm api:types
    git diff --exit-code -- src/api/schema.d.ts
    pnpm build-only
    pnpm size
    pnpm check:licenses
    pnpm audit --prod --audit-level high

# Python, Debian, Node.js, PostgreSQL, Django: fails 180 days before their support ends.
# Not in `check`: it needs the network and its result changes with the date (weekly in CI).
[working-directory: 'backend']
check-eol:
    uv run --no-project python scripts/check_eol.py

# GitHub workflows: syntax (actionlint) and security (zizmor)
check-workflows:
    uvx --from actionlint-py==1.7.12.25 actionlint
    uvx zizmor@1.32.0 .github/

# --- Docker ----------------------------------------------------------------------------

# Build the image locally and start the production stack (compose.yml, http://127.0.0.1:6326)
docker-up $APP_IMAGE="meanwhile":
    docker build -t meanwhile .
    docker compose up -d

# Dump the database now (the worker does it nightly)
docker-backup:
    docker compose exec worker python manage.py backup_database

docker-logs:
    docker compose logs -f app worker

docker-down:
    docker compose down
