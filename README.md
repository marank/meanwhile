# Calendar

A self-hosted calendar application with a Django backend and a Vue 3 frontend.

## Features

- Multiple calendars per user with role-based membership (owner / editor / contributor / viewer).
- Bookable resources per calendar with optional approval workflow.
- Recurring events via RRULE.
- Nested folders for personal sidebar organization.
- Per-calendar iCal feed with unguessable token URL.
- Embedded CalDAV server (Radicale) with optional app passwords.
- English and German UI locales.

## Tech stack

- **Backend**: Python 3.12, Django 5.1, Django Ninja, django-allauth headless, Radicale.
- **Frontend**: Vue 3, Vite, TypeScript, Pinia, Vue Router, vue-i18n, Tailwind CSS.
- **Databases**: SQLite for development, PostgreSQL for deployment.
- **Package managers**: `uv` (backend), `pnpm` (frontend).

## Project structure

```text
calendar/
  backend/            Django backend
  backend_fastapi/    Reference FastAPI implementation
  frontend/           Vue SPA
  docker-compose.yml  PostgreSQL + backend setup
  BACKLOG.md          Feature backlog and known limitations
```

## Backend development

```bash
cd backend
uv sync
DJANGO_SETTINGS_MODULE=config.settings uv run python manage.py migrate
DJANGO_SETTINGS_MODULE=config.settings uv run python manage.py runserver 0.0.0.0:8000
```

Run system checks:

```bash
DJANGO_SETTINGS_MODULE=config.settings uv run python manage.py check
```

## Frontend development

```bash
cd frontend
pnpm install
pnpm dev
```

Build for production:

```bash
pnpm build
```

Checks:

```bash
pnpm test:unit      # Vitest
pnpm lint           # ESLint (fixes what it can)
pnpm format         # Prettier
pnpm type-check     # vue-tsc
```

The Vite dev proxy forwards `/api`, `/ics` and `/caldav` to `http://localhost:8000`.

## Configuration

Backend settings are read from environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | SQLite file | e.g. `postgresql://calendar:calendar@localhost:5432/calendar` |
| `SECRET_KEY` | dev key | Change in production (>= 32 bytes). |
| `ALLOW_REGISTRATION` | `true` | Set to `false` to disable new registrations. |
| `ADMIN_EMAIL` | - | First registered user matching this email is promoted to admin. |
| `CALDAV_PATH` | `/caldav` | URL prefix for the embedded CalDAV server. |

## Authentication

The SPA uses session-cookie authentication via `django-allauth` headless browser endpoints mounted at `/api/auth/v1/auth/`. The frontend fetches a CSRF cookie from `/api/auth/csrf/` before login/register requests.

## CalDAV

CalDAV clients can connect to `/caldav`. Use the email as username and either the account password or a generated app password. If any app password exists for a user, the account password is rejected for CalDAV.

## iCal feed

Each calendar has a feed at `/ics/{feed_token}.ics`. The token can be rotated from the calendar settings.

## Deployment with Docker

```bash
docker compose up --build
```

This starts PostgreSQL and the backend on port 8000. Make sure `SECRET_KEY` is set in your environment.
