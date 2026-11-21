# Meanwhile

Meanwhile is a self-hosted group calendar with a Django backend and a Vue 3 frontend, shipped as
one hardened container image (`ghcr.io/marank/meanwhile`). Licensed under the
[AGPL-3.0-or-later](LICENSE).

## Features

- Multiple calendars per user with role-based membership (owner / full access / own / read only).
- Bookable resources per calendar with optional approval workflow.
- Recurring events via RRULE.
- Nested folders for personal sidebar organization.
- Per-calendar iCal feed with unguessable token URL.
- Email notifications with per-user choices, and invitations by email (iMIP) that participants answer from their mail program or a link.
- Embedded CalDAV server (Radicale) with optional app passwords.
- English and German, in the app and in emails.

## Tech stack

- **Backend**: Python 3.14, Django 6.1, Django Ninja, django-allauth headless, Radicale, Django Channels (WebSockets), served over ASGI by uvicorn.
- **Frontend**: Vue 3, Vite, TypeScript, Pinia, Vue Router, vue-i18n, Tailwind CSS.
- **Database**: PostgreSQL in Docker, CI and production, where it also holds the task queue (procrastinate); SQLite for native development.
- **Tools**: `uv` (backend), `pnpm` (frontend), [`just`](https://just.systems) (every command).

## Project structure

```text
meanwhile/
  backend/            Django backend (config/, apps/core/, locale/de, scripts/ with the CI checks)
  frontend/           Vue SPA
  branding/           Logo (logo.svg; logo-alt.svg is the spare design) and build.sh, which renders
                      favicon and home screen icons into frontend/public/ and the logo emails
                      carry into backend/apps/core/assets/
  scripts/            sync_env.py: brings a .env up to date with .env.example
  docker/             nginx, supervisord, entrypoint, worker, healthcheck and smoke test of the image
  justfile            Every command: development, checks (= CI), API types, migrations, Docker
  Dockerfile          Production image (frontend + backend; app and worker containers)
  compose.yml         Production: PostgreSQL, Redis, app, worker (with nightly backups)
  compose.dev.yml     PostgreSQL, Redis and Mailpit next to the natively run app (`just services`)
  .github/            CI (checks, multi-platform image, smoke test, scans), releases, Dependabot
  AGENTS.md           Conventions for contributors and coding agents (CLAUDE.md imports it)
  CONTRIBUTING.md     How to contribute: checks, Conventional Commits
  BACKLOG.md          Feature backlog and known limitations
```

## Contributing

Meanwhile is still in active development, so pull requests are not accepted yet; bug reports
and ideas are welcome as issues. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Development

Prerequisites: [uv](https://docs.astral.sh/uv/), Node.js 24 with pnpm (`corepack enable` or
`npm install -g pnpm`), and just (`uv tool install rust-just`, `winget install Casey.Just` or
`brew install just`), and GNU gettext for the translation checks (`winget install
mlocati.GetText`, `brew install gettext`, `apt install gettext`). Docker only for the image and
the optional services.

```bash
cp .env.example .env     # once, in the project root (DEBUG=true; ADMIN_* give you a user to sign in with)
just setup               # uv sync + pnpm install
just dev-backend         # migrations, admin user, Django on :8000 (SQLite in backend/data)
just dev-frontend        # in a second terminal: Vite on http://localhost:6326
```

In VS Code the task `dev` starts both; every task only calls a just recipe (`just` lists them).

Natively there is no database server and no worker: the backend uses SQLite, and jobs (emails)
run right after the request's transaction. Periodic jobs (reminders, iMIP answers, clean-ups,
backups) don't run. To run like CI and production, start PostgreSQL, Redis and Mailpit, then the
worker:

```bash
just services           # compose.dev.yml; then in .env: DB_HOST=localhost, REDIS_URL=redis://localhost:6379/0
just dev-worker         # the task queue's worker (apps/core/tasks.py)
```

Without `DEBUG=true` the backend runs as in production: it refuses to start without a real
`SECRET_KEY`. The tests always use development settings (`config/settings_test.py`):

```bash
cd backend && uv run pytest
```

They run in parallel (pytest-xdist); `uv run pytest -n 0` runs them in one process, e.g. to debug
with `-s` or `--pdb`. Natively on SQLite, with `DB_HOST` on PostgreSQL like CI.

### Everyday commands

| Command | When |
| --- | --- |
| `just check` | Before every push: exactly what CI runs (backend, deploy settings, frontend, workflows) |
| `just api-types` | After API changes: schema → `frontend/openapi.json` → `src/api/schema.d.ts`; commit both |
| `just migrations` | After model changes; commit the migrations |
| `just messages` | After new backend texts; translate `backend/locale/de/LC_MESSAGES/django.po` |
| `just sync-env` | After pulling: adds new entries of `.env.example` to `.env` |

Fast checks before each commit: `uv tool run pre-commit install` once.

### Superusers (Django admin)

Superusers may sign in to the Django admin (`/django-admin/`) and do everything there. The app doesn't
hand this out; the admin user of `ADMIN_EMAIL` is one, and others are made (or no longer) with:

```bash
uv run python manage.py set_superuser someone@example.com
uv run python manage.py set_superuser someone@example.com --revoke
```

In production: `docker compose exec app python manage.py set_superuser ...`.

## Frontend development

`just dev-frontend` runs Vite; in `frontend/`:

```bash
pnpm test:unit      # Vitest
pnpm lint           # oxlint, ESLint, knip (unused files, exports, dependencies)
pnpm lint:fix       # oxlint and ESLint, fixing what they can
pnpm format         # Prettier
pnpm type-check     # vue-tsc
```

The Vite dev proxy forwards `/api`, `/django-admin`, `/django-static`, `/ics`, `/caldav` and `/ws` to
`http://localhost:8000`, keeping the browser's `Host`.

## Configuration

Backend settings are read from environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `APP_URLS` | `http://localhost:6326` | Every URL the app is opened under, comma separated. Allowed hosts and CSRF trusted origins come from it; the first is the app's address in emails and feed links. With https URLs only, cookies are secure and plain http is redirected to https. In DEBUG the dev servers are added. |
| `DEBUG` | `false` | `true` for native development: the dev `SECRET_KEY`, the defaults marked as such below (`.env.example` sets it; compose.yml always sets `false`). |
| `SECRET_KEY` | dev key in DEBUG | At least 40 random characters; the app refuses to start with a placeholder. |
| `DB_HOST` | - | PostgreSQL server; compose.yml sets `db`. Empty: SQLite in `DATA_DIR`, no task queue (native development). |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` | `meanwhile`, `meanwhile`, -, `5432` | PostgreSQL login (with `DB_HOST`). |
| `BACKUP_DIR`, `BACKUP_TIME`, `BACKUP_KEEP_DAYS` | `/backups` in the image, `01:30`, `14` | Nightly dump by the worker: directory (empty: off), time of day in `TIME_ZONE`, days to keep. |
| `WEB_WORKERS`, `WORKER_CONCURRENCY` | `4`, `4` | uvicorn processes in the app; jobs the worker runs at once. |
| `ADMIN_ENABLED` | value of `DEBUG` | Serve the Django admin under `/django-admin/`. |
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
them; while the mail server fails, it tries again for about two hours. They carry the logo (the
uploaded one if it is a PNG, JPEG or GIF of up to 200 KB, else ours) as an inline image, which mail
programs show without loading anything.

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
- with the links in the email, which open `/invitation/<token>` in the app, no account needed. The
  page shows the event with who else is invited (by name only: anyone with the link can open it)
  and offers it as a file for calendar apps. The link only preselects the answer; a click on the
  page gives it (mail scanners open links). Opened by the participant while signed in, the page
  leads to the event in the app (`/event/<id>`, where notifications lead too), or, where they can't
  see its calendar, is shown with navbar and sidebar.

The organizer is told of every answer in the app (and by email, as chosen).

```bash
uv run python manage.py fetch_imip
```

### Testing emails in development

[Mailpit](https://mailpit.axllent.org/) catches every email and shows it in the browser:

```bash
just services   # with PostgreSQL and Redis; Mailpit: SMTP on 1025, web UI on http://localhost:8025
```

The backend sends there with `EMAIL_HOST=localhost`, `EMAIL_PORT=1025`, `EMAIL_USE_TLS=false` and
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

In development nothing extra is needed: uvicorn (`just dev-backend`) serves WebSockets, and the
Vite dev server passes `/ws` on.

## Deployment with Docker

On the server, next to each other: `compose.yml` and `.env.example` (as `.env`) from this
repository; nothing else is needed.

```bash
cp .env.example .env     # fill in; DEBUG has no effect here, SECRET_KEY and DB_PASSWORD as described there
docker compose up -d
```

This pulls `ghcr.io/marank/meanwhile:latest` (`APP_IMAGE` pins a version, e.g.
`ghcr.io/marank/meanwhile:1.2`) and starts PostgreSQL, Redis and the image twice:

- `app`: on every start, `docker/entrypoint.sh` checks the production settings
  (`manage.py check --deploy`), applies the migrations and creates or updates the admin user of
  `ADMIN_EMAIL` (`manage.py ensure_admin`). Then supervisord (`docker/supervisord.conf`) runs:
  - nginx (`docker/app.conf.template`, port 8080 inside the container), which serves the built
    frontend and Django admin's static files and passes `/api`, `/ics`, `/caldav`,
    `/.well-known/caldav` and the WebSocket `/ws/` on (`/django-admin` only with `ADMIN_ENABLED=true`);
  - uvicorn, with `WEB_WORKERS` processes.
  If one of them keeps failing, the container stops and Docker restarts it.
- `worker` (`docker/worker`): waits for the app's migrations, then runs the task queue. It sends
  emails, delivers reminders, reads participants' answers from the iMIP mailbox (with
  `IMIP_ADDRESS` and the IMAP settings), cleans up and dumps the database nightly. Jobs wait in the
  database, so none is lost while it restarts.

Every container but the database is hardened: read-only root filesystem, no capabilities, no
privilege escalation, unprivileged users. The app writes only to `/tmp` (tmpfs) and `/data`, the
worker also to `/backups` (volumes). Anything new that needs to write goes there, rather than
loosening `compose.yml`.

`.env` holds the URLs, the secrets, the mail settings and a few optional values; see
`.env.example`. `compose.yml` sets the wiring itself: `DEBUG=false`, `DB_HOST`, `REDIS_URL`.

To check that an image was built by this repository's CI:
`gh attestation verify oci://ghcr.io/marank/meanwhile:latest --owner marank`.

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

The worker dumps the database every night at `BACKUP_TIME` (in `TIME_ZONE`) into the `backups`
volume and keeps `BACKUP_KEEP_DAYS` days. Dumps on the same host don't protect against losing the
host, so copy them off regularly (or point the host's backup at the volume):

```bash
docker compose exec worker python manage.py backup_database                  # a dump right now, e.g. before an update
docker compose cp worker:/backups ./backups                                   # copy all off the container
docker compose exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < file.dump   # restore
```

### Updating

`docker compose pull && docker compose up -d`. New versions may bring new settings:
`python3 scripts/sync_env.py` (natively `just sync-env`) brings `.env` up to date with
`.env.example`: same order and explanations, your values unchanged, new settings added commented
out (their defaults apply until you set them), and settings that are gone listed at the end. The
old file stays as `.env.bak`; `--dry-run` only shows the changes.

Installations from before the GitHub move built the image themselves and had a `backup` service:
its old dumps stay in the `backups` volume under `backups/`; new ones go to the volume's root.
Remove the orphaned service with `docker compose up -d --remove-orphans`.

## Releases and CI

Pull requests are squash-merged with a [Conventional Commit](https://www.conventionalcommits.org/)
title (CONTRIBUTING.md). release-please (`.github/workflows/release.yaml`) keeps a release pull
request up to date with CHANGELOG.md and the next version; merging it tags `vX.Y.Z` and pushes the
image as `X.Y.Z`, `X.Y` and `X`.

`.github/workflows/build.yaml` runs `just check-backend` (on PostgreSQL), `check-deploy`,
`check-frontend` and `check-workflows`, scans the repository (Trivy), then builds the image on
amd64 and arm64, smoke-tests app and worker hardened against a throwaway PostgreSQL
(`docker/smoke-test`), scans it and pushes one multi-platform image with a provenance
attestation (`latest` and `sha-…` from `main`). `main` is rebuilt weekly for Debian's security
fixes. Dependabot proposes updates weekly; AGENTS.md lists what it doesn't cover.

Set up once on GitHub:

1. **Ruleset for `main`**: pull requests required, squash merge only (PR title as commit message),
   required status checks `backend`, `frontend`, `workflows`, `repository`, both `image` jobs and
   `dependency-review`.
2. **Actions → General**: allow GitHub Actions to create and approve pull requests (release-please).
3. **Advanced Security**: private vulnerability reporting, Dependabot alerts, secret scanning with
   push protection, CodeQL default setup.
4. **Releases**: immutable releases on.
5. **Package**: after the first push, make `ghcr.io/marank/meanwhile` public and link it to the
   repository.

### TLS proxy examples

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
