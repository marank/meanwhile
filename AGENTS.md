# Meanwhile — conventions for contributors and coding agents

A self-hosted group calendar: Django backend (`backend/`, API via Django Ninja, CalDAV via an
embedded Radicale), Vue 3 + TypeScript SPA (`frontend/`), one hardened Docker image. Read this
before changing structure; `README.md` has setup and commands, `BACKLOG.md` what's planned.

## Commands

VS Code tasks (`.vscode/tasks.json`) hold the everyday commands; the README lists the plain equivalents.
- `dev: services` (PostgreSQL, Redis, Mailpit of `compose.dev.yml`), then `dev`: Django :8000 +
  Vite :6326 → http://localhost:6326. Native runs need `DEBUG=true`.
- `check` runs everything CI runs (`.gitea/workflows/build.yaml`) and must pass before pushing.
  Change a check in one place, change it in the other.
- `api: types` after any API change (schema → `frontend/openapi.json` → `frontend/src/api/schema.d.ts`);
  commit both. CI fails when they drift.
- `django: makemigrations` after model changes; commit the migrations.
- Frontend: **pnpm** only. Backend: `uv add` / `uv add --dev`. Renovate keeps versions current.

## Backend rules

- One app, `core`. Modules are packages with one file per area: `models/`, `views/` (a Ninja router
  per resource, mounted in `core/api.py`), `services/` (the logic: writes, permissions, recurrence,
  iCal/iTIP, mail), `caldav/` (Radicale plugins), `realtime/` (WebSockets), `tests/`. Request and
  response types live in `core.schemas`. Views stay thin; logic goes into `services/`.
- **Primary keys are UUIDv7** (`core.models.base.UUIDModel`). Exceptions are deliberate:
  the `AppSettings` singleton and the internal log tables `DeletedEvent`, `ReminderDelivery`.
- API: under `/api/`, no trailing slashes, session auth + CSRF (allauth headless under
  `/api/auth/`), UUIDs in paths. `/api/health` stays unauthenticated and exactly at that path.
  PATCH: left out means unchanged; `null` only where a field may really be empty.
- Side effects run after the commit: emails and other jobs go through the task queue
  (procrastinate, `core/tasks.py`), live updates through `core/realtime/broadcast.py`. Changes made
  over CalDAV must notify and broadcast like changes made in the app.
- Permissions are checked in `core/services/permissions.py` and `memberships.py`, never only in
  the frontend.
- User-facing texts in emails come in English and German (`core/services/mail_texts.py`).
- Configuration only via environment variables read through `config/env.py`; every new variable
  gets a commented entry in `.env.example`. No secrets with placeholder values in production.
- mypy must pass (django-stubs); type new code. Coverage stays ≥ 90 %. Tests run against
  PostgreSQL, in parallel (`-n auto`).
- No GPL/AGPL/SSPL dependencies (CI license check). Radicale (GPL-3.0) is the one deliberate
  exception: fine while the app is only run, not handed to others.

## Dates and times

- Everything is stored in UTC; each event keeps its own time zone (for recurrence across DST).
- **All-day events**: start and end are midnight UTC. Stored events have an **inclusive** end;
  occurrences from the events API an **exclusive** one (FullCalendar's convention). Show the UTC
  date (`formatCalendarDate`), never convert all-day values to local time.

## Frontend rules

- Folders by kind: `components/` (by area: `event/`, `calendar/`, `calendar-settings/`, `admin/`,
  `account/`), `views/`, `stores/` (Pinia), `services/` (pure logic, tested on its own),
  `composables/`. Keep components to one job; move logic into services or composables.
- API calls only through `src/api/` (`client.ts` sends the CSRF header, `index.ts` one function per
  endpoint). Types come from the generated `src/api/schema.d.ts`; never edit it by hand.
- Every user-facing text through vue-i18n, in `src/i18n/locales/en.ts` **and** `de.ts`
  (a test checks both have the same keys).
- Tailwind for styling. No inline `<script>`, no remote scripts or styles: the CSP only allows our origin.
- Expose state semantically (`aria-pressed`, `aria-current`, `aria-expanded`, `data-*`) rather than
  only through classes; tests check those, not Tailwind classes.

## Tests

- Test behaviour, not implementation: click and type, then check what is shown and which requests
  go out. Frontend specs use the fake backend (`src/__tests__/fakeBackend.ts`) with fixtures typed
  by the generated API types; make fixtures look like what the backend really sends.
- A bug fix comes with a test that fails without it.
- Frontend coverage gate: 95/95/95/90 (lines/statements/functions/branches).

## Docker / runtime

- The app container runs read-only, without capabilities, as the unprivileged user `app`. Only
  `/data` (`DATA_DIR`) and `/tmp` are writable; new features write there instead of loosening
  `compose.yml`. The dev images (`*/Dockerfile.dev`) run as root on purpose (rootless Docker).
- supervisord runs nginx, uvicorn (ASGI: API, CalDAV, WebSockets) and the task queue's worker; if
  one keeps failing, the container stops.
- nginx believes `X-Forwarded-*` only from `TRUSTED_PROXIES`. It sends no HSTS: the proxy in front
  owns that. `/admin` is closed unless `ADMIN_ENABLED=true`.
