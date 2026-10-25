# Meanwhile

Meanwhile is a self-hosted calendar application with a Django backend and a Vue 3 frontend.

## Features

- Multiple calendars per user with role-based membership (owner / full access / own / read only).
- Bookable resources per calendar with optional approval workflow.
- Recurring events via RRULE.
- Nested folders for personal sidebar organization.
- Per-calendar iCal feed with unguessable token URL.
- Email notifications with per-user choices, and invitations by email (iMIP) that participants answer from their mail program or a link.
- Embedded CalDAV server (Radicale) with optional app passwords.
- English and German UI locales.

## Tech stack

- **Backend**: Python 3.14, Django 6.0, Django Ninja, django-allauth headless, Radicale, Django Channels (WebSockets), served over ASGI (daphne in development, uvicorn in production).
- **Frontend**: Vue 3, Vite, TypeScript, Pinia, Vue Router, vue-i18n, Tailwind CSS.
- **Database**: PostgreSQL, in development too; it also holds the task queue (procrastinate).
- **Package managers**: `uv` (backend), `pnpm` (frontend).

## Project structure

```text
calendar/
  backend/            Django backend
  backend_fastapi/    Reference FastAPI implementation
  frontend/           Vue SPA
  docker/             nginx, supervisord, entrypoint, healthcheck and backup script of the production image
  Dockerfile          Production image (frontend + backend in one container)
  compose.yml         Production: PostgreSQL, Redis, app, nightly backups
  compose.dev.yml     Development stack with live reload
  .gitea/workflows/   CI (checks, image build, smoke test, scans, push) and Renovate
  BACKLOG.md          Feature backlog and known limitations
  AGENTS.md           Conventions for contributors and coding agents (CLAUDE.md imports it)
```

## Development with Docker

The whole stack with live reload: PostgreSQL, Redis, Mailpit, the backend (`runserver`), the
task queue's worker and the Vite dev server.

```bash
cp .env.example .env     # once; ADMIN_EMAIL and ADMIN_PASSWORD give you a user to sign in with
docker compose -f compose.dev.yml up --build
```

The app is at http://localhost:6326, the backend at http://localhost:8000, the emails at
http://localhost:8025. The source is mounted into the containers: `runserver` and the worker
(through `watchfiles`) restart on changes to Python files, Vite updates the page right away.
Migrations run on every start (service `migrate`), followed by `manage.py ensure_admin`. After changing dependencies (`uv.lock`,
`pnpm-lock.yaml`), start it again with `--build`; the frontend installs its packages on start.

Commands run in the backend's container:

```bash
docker compose -f compose.dev.yml exec backend pytest
docker compose -f compose.dev.yml exec backend python manage.py fetch_imip --mailpit http://mailpit:8025
```

All setups read the `.env` of the project root (template: `.env.example`).
`compose.dev.yml` sets the database, Redis and Mailpit addresses itself, overriding it.

## Backend development

Without Docker for the app itself, only the services next to it:

```bash
docker compose -f compose.dev.yml up -d postgres redis mailpit   # the default database, Redis, Mailpit
cp .env.example .env     # once, in the project root; set DEBUG=true there
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000
```

Without `DEBUG=true` the backend runs as in production: it refuses to start without a real
`SECRET_KEY` and `DB_PASSWORD`. The tests always use development settings (`config/settings_test.py`).
In VS Code, the tasks `dev: services` and `dev` do the same.

In a second terminal, the worker of the task queue: it sends emails, delivers reminders and runs
the other regular jobs (`core/tasks.py`).

```bash
uv run python manage.py procrastinate worker
```

The tests need the PostgreSQL of `compose.dev.yml`, too:

```bash
uv run pytest
```

They run in parallel, one process per CPU (pytest-xdist); `uv run pytest -n 0` runs them in one,
e.g. to debug with `-s` or `--pdb`. The test settings (`config/settings_test.py`) use a fast password
hasher and no delay for wrong CalDAV passwords.

### Superusers (Django admin)

Superusers may sign in to the Django admin (`/admin/`) and do everything there. The app doesn't
hand this out; the admin user of `ADMIN_EMAIL` is one, and others are made (or no longer) with:

```bash
uv run python manage.py set_superuser someone@example.com
uv run python manage.py set_superuser someone@example.com --revoke
```

In the Docker setups: `docker compose exec app python manage.py set_superuser ...` (production),
`docker compose -f compose.dev.yml exec backend python manage.py set_superuser ...`
(development).

### Checks

The VS Code task `check` runs everything CI runs (`.gitea/workflows/build.yaml`); keep both in
sync. Without VS Code, in `backend/` (with `DEBUG=true` and the services above running):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run deptry .
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check --fail-level WARNING
uv run pytest -q --cov --cov-fail-under=90
```

And in `frontend/`: `pnpm check` (Prettier, oxlint, ESLint, knip, vue-tsc, Vitest with its coverage
minimum), `pnpm build-only && pnpm size` (bundle budget) and `pnpm check:licenses`.

Fast checks before each commit: `uv tool run pre-commit install` once.

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
pnpm lint           # oxlint, ESLint, knip (unused files, exports, dependencies)
pnpm lint:fix       # oxlint and ESLint, fixing what they can
pnpm format         # Prettier
pnpm type-check     # vue-tsc
```

The Vite dev proxy forwards `/api`, `/admin`, `/django-static`, `/ics`, `/caldav` and `/ws` to
`http://localhost:8000` (`BACKEND_URL` changes it), keeping the browser's `Host`.

## Configuration

Backend settings are read from environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `APP_URLS` | `http://localhost:6326` | Every URL the app is opened under, comma separated. Allowed hosts and CSRF trusted origins come from it; the first is the app's address in emails and feed links. With https URLs only, cookies are secure and plain http is redirected to https. In DEBUG the dev servers are added. |
| `DEBUG` | `false` | `true` for running the backend without Docker: DEBUG, the dev `SECRET_KEY` and database password, the defaults marked as such below. |
| `SECRET_KEY` | dev key in DEBUG | At least 40 random characters; the app refuses to start with a placeholder. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | `meanwhile`, `meanwhile`, `meanwhile` in DEBUG, `localhost`, `5432` | PostgreSQL only (the one of `compose.dev.yml` by default). |
| `ADMIN_ENABLED` | value of `DEBUG` | Serve the Django admin under `/admin/`. |
| `TIME_ZONE`, `LANGUAGE_CODE` | `UTC`, `en-us` | Server defaults; users choose their own zone and language in the app. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `DATA_DIR` | `backend/data` | Writable data directory; `/data` in the container. |
| `ALLOW_REGISTRATION` | value of `DEBUG` | Whether anyone may sign up. Signed-in users can look each other up (by name and email) to share calendars, so only open it to people who may see each other. |
| `ADMIN_EMAIL` | - | The admin user. `manage.py ensure_admin` (run on every start of the Docker setups) creates it or makes the existing user of that address admin (who then loses their sessions and app passwords to `ADMIN_PASSWORD`). Signing up never makes anyone admin; without Docker, run `manage.py ensure_admin` once. |
| `ADMIN_PASSWORD` | - | Password of the admin user; needed to create it or make an existing user admin, set again when it differs (which signs the admin out). Empty: an existing admin keeps their password. Outside DEBUG it must pass the password rules and must not be a placeholder. |
| `ADMIN_NAME` | - | Display name of the admin user. |
| `CALDAV_PATH` | `/caldav` | URL prefix for the embedded CalDAV server. |
| `REDIS_URL` | - | e.g. `redis://redis:6379/0`. Required with more than one server process, so that live updates reach every process's WebSockets. Without it they stay within one process (fine for development). |
| `WEBSOCKET_PATH` | `/ws/` | Path of the live update WebSocket. |
| `EMAIL_HOST`, `EMAIL_PORT` | -, `587` | SMTP server. Without it, emails are printed to the console in development and not sent otherwise. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | - | SMTP login. |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | `false` | STARTTLS (usually port 587) / implicit TLS (usually 465). |
| `DEFAULT_FROM_EMAIL` | `meanwhile@localhost` | Sender address of all emails. |
| `IMIP_ADDRESS` | - | Mailbox that receives participants' answers to invitations; invitations name it as organizer. Empty: answers go to the organizer's own address. |
| `IMIP_IMAP_HOST`, `IMIP_IMAP_PORT`, `IMIP_IMAP_USER`, `IMIP_IMAP_PASSWORD`, `IMIP_IMAP_SSL`, `IMIP_IMAP_FOLDER` | -, `993`, -, -, `true`, `INBOX` | IMAP access to that mailbox; the worker reads it every five minutes. |
| `IMIP_TRUSTED_AUTHSERV_ID` | - | The name your receiving mail server writes into its `Authentication-Results` header (e.g. `mx.example.com`). Set, answers by email count only if that server verified the sender's domain (DMARC, or a DKIM signature of that domain); otherwise anyone who knows a participant's address could answer for them. |

## Authentication

The SPA uses session-cookie authentication via `django-allauth` headless browser endpoints mounted at `/api/auth/v1/auth/`. The frontend fetches a CSRF cookie from `/api/auth/csrf` before login/register requests.

## CalDAV

CalDAV clients can connect to `/caldav`; clients that only get the server address find it via `/.well-known/caldav`. Use the email as username and either the account password or a generated app password. If any app password exists for a user, the account password is rejected for CalDAV.

Every calendar a user can access appears in their calendar home, shared ones included. Clients can create calendars there and their owners can delete them. Categories, the booked resource (as location) and participants are synchronized; each user's reminders appear as alarms in their own clients only. Times sent without a zone are read in the user's zone, which the web app keeps up to date from the browser.

## Reminders

Users set their own reminders per event. The worker looks for due reminders every 30 seconds and
turns them into in-app notifications, which pop up in all of the user's open tabs (over the live
connection, see below). `manage.py send_reminders` does the same once, by hand.

## Email and invitations

Notifications can also come by email: approval requests, decisions on bookings, comments, calendar
access, participants' answers and (off by default) reminders. Each user chooses which in
*Account → Email notifications*. Emails are written in the user's language and show times in their
zone. They are saved as jobs of the task queue along with the request's changes, and the worker sends
them; while the mail server fails, it tries again for about two hours.

Participants of an event are invited by email (iMIP, RFC 6047): the email carries the event as
iTIP `REQUEST`, inline and as `invite.ics`, so Thunderbird, Outlook, Apple Mail, Gmail and others
show it with their accept/decline buttons. Changes are sent as updates (with a higher `SEQUENCE`),
and deleting, cancelling or rejecting the event, or taking a participant off it, sends a `CANCEL`.
Participants without an account are reached this way too. Users with an account who switched
invitations off get them in the app only.

Participants answer either

- in their mail program: it sends an iTIP `REPLY` to the organizer address. With `IMIP_ADDRESS`
  set, that is the app's mailbox, which the worker reads every five minutes (IMAP). An answer
  only counts when it comes from the participant's own address (or the one they named as `SENT-BY`).
  `process_imip FILE.eml` (or `-` for standard input, e.g. from a mail server's pipe) applies saved
  messages; or
- with the links in the email, which open `/rsvp/<token>` in the app, no account needed. The
  link only preselects the answer; a click on the page gives it (mail scanners open links).

The organizer is told of every answer in the app (and by email, as chosen).

```bash
uv run python manage.py fetch_imip
```

### Testing emails in development

[Mailpit](https://mailpit.axllent.org/) catches every email and shows it in the browser:

```bash
docker compose -f compose.dev.yml up -d mailpit   # SMTP on 1025, web UI on http://localhost:8025
```

`compose.dev.yml` sends the backend's emails there by itself. A backend run without Docker
needs `EMAIL_HOST=localhost`, `EMAIL_PORT=1025`, `EMAIL_USE_TLS=false` and
`IMIP_ADDRESS=meanwhile@localhost` in `.env`.

Restart the backend, invite someone (any address) to an event and open the invitation in Mailpit;
its links lead to the answer page of the Vite dev server. To test answers from mail programs,
let a participant answer as their program would, then read the answer from Mailpit:

```bash
cd backend
uv run python manage.py imip_reply <event-id> guest@example.com accepted   # sends an iTIP REPLY to IMIP_ADDRESS
uv run python manage.py fetch_imip --mailpit http://localhost:8025         # reads unread answers from Mailpit
```

`imip_reply --process` applies the answer right away, without a mailbox. Without `EMAIL_HOST`,
emails are printed to the backend's console. `manage.py sendtestemail you@example.com` checks the
SMTP settings.

## iCal feed

Each calendar has a feed at `/ics/{feed_token}.ics`. The token can be rotated from the calendar settings. The feed carries the calendar's name and color, categories and resources, but no participants or reminders, since anyone with the link can read it.

## Live updates

Open calendars, the list of calendars and the notification count update by themselves when something changes: another
user's edit, a change from another tab, or a phone syncing via CalDAV. The browser keeps a
WebSocket to `/ws/`; the server only announces *that* a calendar's events or a user's
notifications changed, and the app loads them again through the API (so each user only ever sees
what their permissions allow).

The connection is kept alive with a heartbeat, reconnects with growing delays after interruptions
(server restart, network change, sleep), and loads what it shows again after reconnecting, so
nothing missed meanwhile is lost. Pages of other sites can't open it (the `Origin` is checked).

Without a working WebSocket (a proxy that doesn't pass it on), the app falls back to fetching the unread count every minute; reminders then only arrive as notifications.

In development nothing extra is needed: `manage.py runserver` serves WebSockets, and the Vite dev
server passes `/ws` on.

## Deployment with Docker

```bash
cp .env.example .env     # fill in; SECRET_KEY and DB_PASSWORD as described there
docker compose up -d --build
```

This starts PostgreSQL, Redis, the `app` container, built by the `Dockerfile`, and `backup`:

- On every start, `docker/entrypoint.sh` checks the production settings
  (`manage.py check --deploy`), applies the migrations and creates or updates the admin user of
  `ADMIN_EMAIL` (`manage.py ensure_admin`).
- Then supervisord (`docker/supervisord.conf`) runs, like everything in the container, as the
  unprivileged user `app`:
  - nginx (`docker/app.conf.template`, port 8080 inside the container), which serves the built
    frontend and Django admin's static files and passes `/api`, `/ics`, `/caldav`,
    `/.well-known/caldav` and the WebSocket `/ws/` on (`/admin` only with `ADMIN_ENABLED=true`);
  - uvicorn, with `WEB_WORKERS` processes;
  - the task queue's worker. It sends emails, delivers reminders, reads participants' answers
    from the iMIP mailbox (with `IMIP_ADDRESS` and the IMAP settings) and cleans up. Jobs wait in
    the database, so none is lost while it restarts.
  If one of them keeps failing, the container stops and Docker restarts it.

The app, Redis and backup containers are hardened: read-only root filesystem, no capabilities,
no privilege escalation, unprivileged users. The app writes only to `/tmp` (tmpfs) and `/data`
(volume). Anything new that needs to write goes there, rather than loosening `compose.yml`.

`.env` holds the URLs, the secrets, the mail settings and a few optional values; see
`.env.example`. `compose.yml` sets the wiring itself: `DEBUG=false`, `DB_HOST`, `REDIS_URL`.

The container serves HTTP on `APP_BIND` (`127.0.0.1:6326` by default). Put a proxy in front that
terminates HTTPS, passes everything on, including WebSocket upgrades, and sets
`X-Forwarded-Proto` and `X-Forwarded-For` (and keeps `Host`, or sets `X-Forwarded-Host`). The app
sends no HSTS header; set it at that proxy if you want it.

nginx in the container believes those headers only when the request comes from one of
`TRUSTED_PROXIES` (default: the private networks `10.0.0.0/8`, `172.16.0.0/12`,
`192.168.0.0/16`, `fc00::/7`, which covers a proxy on the host reaching the container through
Docker's network); from anyone else they are ignored. With `https://` in `APP_URLS`, plain http
is redirected, so the proxy must be listed, or every request ends in a redirect loop. Failed logins
are limited per client address (by nginx, 10 per minute, and by allauth), so a proxy elsewhere has
to be listed there too, e.g. `TRUSTED_PROXIES=203.0.113.10`; `none` trusts no proxy.

### Backups

The `backup` service dumps the database every night at `BACKUP_TIME` (in `TIME_ZONE`) into the
`backups` volume and keeps `BACKUP_KEEP_DAYS` days. Dumps on the same host don't protect against
losing the host, so copy them off regularly:

```bash
docker compose exec backup sh /backup.sh now                                   # a dump right now
docker compose cp backup:/var/lib/postgresql/backups ./backups                 # copy all off the container
docker compose exec -T backup sh -c 'pg_restore --clean --if-exists -d "$PGDATABASE"' < file.dump   # restore
```

### Upgrading an existing installation

The configuration changed: in `.env`, rename `POSTGRES_PASSWORD` to `DB_PASSWORD` and replace
`DOMAIN=meanwhile.example.com` with `APP_URLS=https://meanwhile.example.com`. `ENVIRONMENT`,
`BEHIND_PROXY`, `SECURE_COOKIES`, `BASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and
`CORS_ORIGINS` are gone (`DEBUG` and `APP_URLS` replace them). `SECRET_KEY` must be at least 40
characters, and `ADMIN_PASSWORD` must pass the password rules. The database volume keeps its name.

### CI and Renovate (Gitea)

`.gitea/workflows/build.yaml` checks backend and frontend, scans the repository (Trivy), builds
the image, starts it hardened against a throwaway PostgreSQL, scans it and pushes it to the Gitea
registry of this instance (`latest` and `sha-…` from `main`, versions from `v1.2.3` tags).
`renovate.yaml` runs Renovate daily (`renovate.json`): minor and patch updates merge themselves
once CI is green, majors wait for a look.

Set up once in Gitea:

1. **Branch protection on `main` with required status checks** `backend`, `frontend`,
   `repository` and `image`. Renovate's automerge waits for them; without required checks Gitea
   merges right away, even with red CI.
2. Actions enabled for the repository, and a runner with Docker.
3. Secrets: `REGISTRY_USER` and `REGISTRY_TOKEN` (scope `write:package`) for the image;
   `RENOVATE_TOKEN` (`write:repository`, `write:issue`, `read:organization`, `read:user`,
   `read:package`) and optionally `GH_COM_TOKEN` (a read-only github.com token, for release notes)
   for Renovate.

Caddy (obtains the certificate itself):

```caddy
meanwhile.example.com {
    reverse_proxy 127.0.0.1:6326
}
```

nginx:

```nginx
server {
    listen 443 ssl;
    server_name meanwhile.example.com;
    # ssl_certificate ...; ssl_certificate_key ...;

    location / {
        proxy_pass http://127.0.0.1:6326;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 10m;
        # Longer than the app's heartbeat (25 s), so idle WebSockets stay open.
        proxy_read_timeout 120s;
    }
}
```
