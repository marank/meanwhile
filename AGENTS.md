# Meanwhile — conventions for contributors and coding agents

A self-hosted group calendar: Django backend (`backend/`, API via Django Ninja, CalDAV via an
embedded Radicale), Vue 3 + TypeScript SPA (`frontend/`), one hardened Docker image for the app
and the worker. Read this before changing structure; `CONTRIBUTING.md` has setup and commands,
`docs/operations.md` how it runs in production, `BACKLOG.md` what's planned.

## Stack and layout

- Backend: Python 3.14, Django 6.1, Django Ninja, django-allauth headless (browser endpoints under
  `/api/auth/v1/auth/`; the SPA fetches a CSRF cookie from `/api/auth/csrf` first), Radicale,
  Django Channels for WebSockets, all served over ASGI by uvicorn; procrastinate as task queue.
- Frontend: Vue 3, Vite, TypeScript, Pinia, Vue Router, vue-i18n, Tailwind CSS.
- `backend/` (config/, apps/core/, locale/de, scripts/ with the CI checks), `frontend/`,
  `docker/` (nginx, supervisord, entrypoint, worker, healthcheck, smoke test), `branding/` (logo
  and `build.sh`, which renders the favicons into `frontend/public/` and the email logo into
  `backend/apps/core/assets/`), `scripts/sync_env.py`, `docs/` (operations, review decisions).

## Documentation

- `README.md` is for people deciding to use Meanwhile and starting it: features, quick start,
  a short operations list, contributing, license; at most 200 lines, no tech stack, development
  or configuration details.
- Development setup and the release process live in `CONTRIBUTING.md`, how it runs in production
  in `docs/operations.md`, every setting in `.env.example`, conventions here.

## Commands

Every command lives in the `justfile`; CI (`.github/workflows/build.yaml`) and the VS Code tasks
only call its recipes, so a check is changed in one place.
- `just dev` (or `just dev-backend` + `just dev-frontend`; VS Code: `dev`) → http://localhost:6326.
  Natively the backend uses SQLite and runs jobs in-process; `just services` +
  `DB_HOST=localhost` (and `just dev-worker`) run it on PostgreSQL like CI.
- `just check` runs everything CI runs and must pass before pushing.
- `just api-types` after any API change (schema → `frontend/openapi.json` → `frontend/src/api/schema.d.ts`);
  commit both. CI fails when they drift.
- `just migrations` after model changes; commit the migrations.
- `just messages` after new backend texts; translate every entry of `backend/locale/de/LC_MESSAGES/django.po`,
  and in `backend/locale/de_Informal` (German with "du") those whose German says "Sie"/"Ihr".
- Frontend: **pnpm** only. Backend: `uv add` / `uv add --dev`.
- Claude Code formats and lints each file right after editing it (`.claude/settings.json` runs
  `scripts/lint_file.py`); what is left comes back to the agent to fix, not to silence.
- Commits on `main` are Conventional Commits (squash-merged PR titles); release-please makes the
  releases from them.

## Backend rules

- Apps live in `backend/apps/<name>/` (`name="apps.<name>"`, label `<name>`); so far there is one,
  `core`. Modules are packages with one file per area: `models/`, `views/` (a Ninja router per
  resource, mounted in `apps/core/api.py`), `services/` (the logic: writes,
  permissions, recurrence, iCal/iTIP, mail, backups), `caldav/` (Radicale plugins), `realtime/`
  (WebSockets), `tests/`. Request and response types live in `apps.core.schemas`. Views stay thin;
  logic goes into `services/`. import-linter (`lint-imports`) enforces the layers.
- **Primary keys are UUIDv7** (`apps.core.models.base.UUIDModel`); the `core.E001` check enforces it.
  Exceptions are deliberate: the `AppSettings` singleton, the internal log tables
  `DeletedEvent`, `ReminderDelivery`, and one-to-one keys to a UUID model (`OverviewSettings.user`).
- API: under `/api/`, no trailing slashes, session auth + CSRF (allauth headless under
  `/api/auth/`), UUIDs in paths. `/api/health` stays unauthenticated and exactly at that path.
  PATCH: left out means unchanged; `null` only where a field may really be empty.
- Side effects run after the commit: emails and other jobs are deferred only through
  `apps.core.jobs.defer` (never `task.defer()`), which queues them in procrastinate with PostgreSQL and
  runs them in-process after the commit with SQLite; live updates go through
  `apps/core/realtime/broadcast.py`. Changes made over CalDAV must notify and broadcast like changes
  made in the app.
- Code runs on PostgreSQL and SQLite: no PostgreSQL-only fields or lookups.
- Permissions are checked in `apps/core/services/permissions.py` and `memberships.py`, never only in
  the frontend.
- Backend texts are English source strings marked for gettext (emails: `apps/core/services/mail_texts.py`,
  context "email"), German in `backend/locale/de`; `just check` fails on untranslated or fuzzy entries.
- Configuration only via environment variables read through `config/env.py`; every new variable
  gets a commented entry in `.env.example` (its only documentation; behaviour operators need to
  know beyond it goes into `docs/operations.md`). No secrets with placeholder values in production.
- ruff with complexity ≤ 15 and nesting ≤ 4, complexipy with cognitive complexity ≤ 15; split by
  responsibility, never to meet a size. ruff also reports blind `except Exception` (`BLE`, `TRY`; with the reason in a
  comment where it is a deliberate boundary), slow patterns (`PERF`) and longer spellings (`FURB`),
  pytest misuse (`PT`: one condition per `assert`, `raises` with `match`), blanket and unused
  `# noqa` (`PGH`, `RUF100`).
- mypy runs in strict mode (django-stubs), tests included, and also reports checks the types
  rule out (`warn_unreachable`, `redundant-expr`, `truthy-bool`, …): delete such a check; where
  the stubs are narrower than the data, widen the annotation with the reason in a comment.
  `# type: ignore[code]` only with the reason next to it. Coverage stays ≥ 90 %. Tests run in parallel (`-n auto`), natively on SQLite,
  in CI on PostgreSQL.
- Production dependencies must fit the project's AGPL-3.0-or-later (license gate in
  `just check`): permissive, LGPL, GPL-3.0, AGPL-3.0 and GPL-2.0 "or later" are fine;
  GPL-2.0-only, an unversioned GPL, EPL-1.0, CDDL, MPL-1.1, SSPL and missing license
  information are not. Packages with wrong metadata go into the scripts' `ALLOW` with the
  reason (Radicale declares only "GPL"; it is GPL-3.0).
  The services in `compose.yml` (PostgreSQL, Redis under its AGPLv3 option) are separate programs
  the app talks to over the network, not dependencies; their licenses don't reach the app's code.

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
- Every user-facing text through vue-i18n, in `src/i18n/locales/en/<area>.ts` **and** `de/<area>.ts`
  (one file per area; a test checks both have the same keys). `de-informal/<area>.ts` (German with
  "du") holds only the keys whose German says "Sie"/"Ihr", the rest comes from `de`; a test checks that too.
- Tailwind for styling. No inline `<script>`, no remote scripts or styles: the CSP only allows our origin.
- Expose state semantically (`aria-pressed`, `aria-current`, `aria-expanded`, `data-*`) rather than
  only through classes; tests check those, not Tailwind classes.
- ESLint lints with types (typescript-eslint's `recommendedTypeChecked` plus unnecessary conditions,
  `??` and exhaustive switches; sonarjs cognitive complexity ≤ 15). A promise that isn't awaited is
  marked `void`, and only where it handles its own errors. Defaults use `??`; where the server's empty
  string means "none" (names, logo URLs), `nonEmpty(value) ?? fallback` from `services/text.ts`.
  `eslint-disable` only for one line, naming its rules, with the reason after `--`; unused ones fail.
  Also on: `vue/no-v-html`, `vue/no-unused-properties` and eslint-plugin-vuejs-accessibility (labels
  wrap their field; comboboxes keep focus in the field, see `project/comboboxes`). No comment before
  a component's root element: in development it turns the component into a fragment.

## Tests

- Test behaviour, not implementation: click and type, then check what is shown and which requests
  go out. Frontend specs use the fake backend (`src/__tests__/fakeBackend.ts`) with fixtures typed
  by the generated API types; make fixtures look like what the backend really sends.
- A bug fix comes with a test that fails without it.
- Frontend coverage gate: 95/95/95/90 (lines/statements/functions/branches).
- Every test asserts; no `.only` or skipped test is committed (`@vitest/eslint-plugin`). Backend
  tests run in random order (pytest-randomly prints the seed; `--randomly-seed=<seed>` repeats it).
- At most 3 % copied code across frontend and backend sources (`pnpm check:duplication`, jscpd).

## Docker / runtime

- One image, two containers: `app` (supervisord with nginx and uvicorn — ASGI for API,
  CalDAV and WebSockets) and `worker` (`docker/worker`: the task queue and the nightly
  `pg_dump` into `/backups`). If a program in `app` keeps failing, the container stops.
- Both run read-only, without capabilities, as the unprivileged user `app`. Only `/data`
  (`DATA_DIR`), `/backups` (worker) and `/tmp` are writable; new features write there instead of
  loosening `compose.yml`.
- Development is native (`just dev`); `compose.dev.yml` holds only
  the services next to it (PostgreSQL, Redis, Mailpit), no images of the app.
- `compose.yml` works with `.env` alone: no file of the repository is mounted.
- New runtime probes go into `docker/smoke-test`, which CI runs in both containers.
- nginx believes `X-Forwarded-*` only from `TRUSTED_PROXIES`. It sends no HSTS: the proxy in front
  owns that. The Django admin (`/django-admin`) is closed unless `ADMIN_ENABLED=true`; `/admin` is
  the app's own administration page.

## Supply chain

Actions are pinned to commit SHAs, images to tag and digest, lock files are committed; Dependabot
moves them weekly. It does **not** see, so bump by hand now and then:
- `TRIVY_IMAGE` (tag and digest) and `POSTGRES_IMAGE` in `.github/workflows/build.yaml`
  (Postgres together with `compose.yml`).
- `ARG PG_MAJOR` (follows compose's Postgres major) and `ARG SUPERVISOR_VERSION` in the `Dockerfile`.
- actionlint and zizmor in the `justfile`, `rust-just==…` in the workflows.
- pnpm's `packageManager` field, if Dependabot leaves it alone (`pnpm self-update`, commit).
- The pre-commit hooks: `uv tool run pre-commit autoupdate`.

## House defaults

Checked against django-spa-defaults 1.8.0 (2026-11-21).

- Releases: release-please
- Contributions: team only
- ADRs: no
- BE-04: met with a `Lower("email")` unique constraint: the email address is the username
  (`USERNAME_FIELD`), looked up with `__iexact`.
- DOCKER-03: met with `docker/smoke-test` probing `/api/auth/v1/auth/session` for 401, allauth
  headless's counterpart of `/api/auth/me`.
- BE-11: settled: `DEBUG` defaults to off, `config/env.py` refuses a weak `SECRET_KEY` without it.
- BE-13: settled: allauth's emails go out through `mail.send` as jobs; `imip_reply` is a
  development command, not a request.
- BE-14: settled: writes with follow-ups go through `services/` (approvals, members, approvers, users,
  occurrences, participants, comments, layout); views keep plain writes of their own object, whose
  follow-ups (memberships from groups, live updates) run in `signals.py` for the app and CalDAV alike.
