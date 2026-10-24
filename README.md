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

- **Backend**: Python 3.12, Django 5.1, Django Ninja, django-allauth headless, Radicale, Django Channels (WebSockets), served over ASGI (daphne in development, uvicorn in production).
- **Frontend**: Vue 3, Vite, TypeScript, Pinia, Vue Router, vue-i18n, Tailwind CSS.
- **Database**: PostgreSQL, in development too; it also holds the task queue (procrastinate).
- **Package managers**: `uv` (backend), `pnpm` (frontend).

## Project structure

```text
calendar/
  backend/            Django backend
  backend_fastapi/    Reference FastAPI implementation
  frontend/           Vue SPA
  docker/             nginx, supervisord and entrypoint of the production image
  Dockerfile          Production image (frontend + backend in one container)
  docker-compose.yml  Production: PostgreSQL, Redis, app
  docker-compose.dev.yml  Development stack with live reload
  BACKLOG.md          Feature backlog and known limitations
```

## Development with Docker

The whole stack with live reload: PostgreSQL, Redis, Mailpit, the backend (`runserver`), the
task queue's worker and the Vite dev server.

```bash
cp .env.example .env     # once; ADMIN_EMAIL and ADMIN_PASSWORD give you a user to sign in with
docker compose -f docker-compose.dev.yml up --build
```

The app is at http://localhost:6326, the backend at http://localhost:8000, the emails at
http://localhost:8025. The source is mounted into the containers: `runserver` and the worker
(through `watchfiles`) restart on changes to Python files, Vite updates the page right away.
Migrations run on every start (service `migrate`), followed by `manage.py ensure_admin`. After changing dependencies (`uv.lock`,
`pnpm-lock.yaml`), start it again with `--build`; the frontend installs its packages on start.

Commands run in the backend's container:

```bash
docker compose -f docker-compose.dev.yml exec backend pytest
docker compose -f docker-compose.dev.yml exec backend python manage.py fetch_imip --mailpit http://mailpit:8025
```

All setups read the `.env` of the project root (template: `.env.example`).
`docker-compose.dev.yml` sets the database, Redis and Mailpit addresses itself, overriding it.

## Backend development

Without Docker for the app itself, only the services next to it:

```bash
docker compose -f docker-compose.dev.yml up -d postgres redis mailpit   # the default DATABASE_URL, Redis, Mailpit
cp .env.example .env     # once, in the project root; uncomment ENVIRONMENT=development there
cd backend
uv sync
DJANGO_SETTINGS_MODULE=config.settings uv run python manage.py migrate
DJANGO_SETTINGS_MODULE=config.settings uv run python manage.py runserver 0.0.0.0:8000
```

Without `ENVIRONMENT=development` the backend runs as in production: it refuses to start with the
development `SECRET_KEY`. The tests always use development settings (`config/settings_test.py`).

In a second terminal, the worker of the task queue: it sends emails, delivers reminders and runs
the other regular jobs (`core/tasks.py`).

```bash
DJANGO_SETTINGS_MODULE=config.settings uv run python manage.py procrastinate worker
```

The tests need the PostgreSQL of `docker-compose.dev.yml`, too:

```bash
uv run pytest
```

### Superusers (Django admin)

Superusers may sign in to the Django admin (`/admin/`) and do everything there. The app doesn't
hand this out; the admin user of `ADMIN_EMAIL` is one, and others are made (or no longer) with:

```bash
uv run python manage.py set_superuser someone@example.com
uv run python manage.py set_superuser someone@example.com --revoke
```

In the Docker setups: `docker compose exec app python manage.py set_superuser ...` (production),
`docker compose -f docker-compose.dev.yml exec backend python manage.py set_superuser ...`
(development).

### System checks

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

The Vite dev proxy forwards `/api`, `/ics`, `/caldav` and `/ws` to `http://localhost:8000` (`BACKEND_URL` changes it).

## Configuration

Backend settings are read from environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://meanwhile:meanwhile@localhost:5432/meanwhile` | PostgreSQL only (the one of `docker-compose.dev.yml` by default) |
| `ENVIRONMENT` | `production` | `development` for running the backend without Docker: DEBUG, the dev `SECRET_KEY`, the defaults marked as such below. |
| `SECRET_KEY` | dev key | Change in production (>= 32 bytes). |
| `ALLOW_REGISTRATION` | `true` in development, `false` otherwise | Whether anyone may sign up. Signed-in users can look each other up (by name and email) to share calendars, so only open it to people who may see each other. |
| `ADMIN_EMAIL` | - | The admin user. `manage.py ensure_admin` (run on every start of the Docker setups) creates it or makes the existing user of that address admin (who then loses their sessions and app passwords to `ADMIN_PASSWORD`). Signing up never makes anyone admin; without Docker, run `manage.py ensure_admin` once. |
| `ADMIN_PASSWORD` | - | Password of the admin user; needed to create it or make an existing user admin, set again when it differs (which signs the admin out). Empty: an existing admin keeps their password. |
| `ADMIN_NAME` | - | Display name of the admin user. |
| `CALDAV_PATH` | `/caldav` | URL prefix for the embedded CalDAV server. |
| `REDIS_URL` | - | e.g. `redis://redis:6379/0`. Required with more than one server process, so that live updates reach every process's WebSockets. Without it they stay within one process (fine for development). |
| `BEHIND_PROXY` | `false` | Trust the reverse proxy's `X-Forwarded-Proto`/`-Host`. Only when the backend is reachable through the proxy alone. |
| `SECURE_COOKIES` | `true` outside development | Session and CSRF cookies over HTTPS only. |
| `CSRF_TRUSTED_ORIGINS` | Vite dev servers | The public origin(s), e.g. `https://meanwhile.example.com`. |
| `WEBSOCKET_PATH` | `/ws/` | Path of the live update WebSocket. |
| `BASE_URL` | - | Public address of the app, e.g. `https://meanwhile.example.com`; used for feed URLs and links in emails (in development, links point to the Vite dev server). |
| `EMAIL_HOST`, `EMAIL_PORT` | -, `587` | SMTP server. Without it, emails are printed to the console in development and not sent otherwise. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | - | SMTP login. |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | `false` | STARTTLS (usually port 587) / implicit TLS (usually 465). |
| `DEFAULT_FROM_EMAIL` | `meanwhile@localhost` | Sender address of all emails. |
| `IMIP_ADDRESS` | - | Mailbox that receives participants' answers to invitations; invitations name it as organizer. Empty: answers go to the organizer's own address. |
| `IMIP_IMAP_HOST`, `IMIP_IMAP_PORT`, `IMIP_IMAP_USER`, `IMIP_IMAP_PASSWORD`, `IMIP_IMAP_SSL`, `IMIP_IMAP_FOLDER` | -, `993`, -, -, `true`, `INBOX` | IMAP access to that mailbox; the worker reads it every five minutes. |
| `IMIP_TRUSTED_AUTHSERV_ID` | - | The name your receiving mail server writes into its `Authentication-Results` header (e.g. `mx.example.com`). Set, answers by email count only if that server verified the sender's domain (DMARC, or a DKIM signature of that domain); otherwise anyone who knows a participant's address could answer for them. |

## Authentication

The SPA uses session-cookie authentication via `django-allauth` headless browser endpoints mounted at `/api/auth/v1/auth/`. The frontend fetches a CSRF cookie from `/api/auth/csrf/` before login/register requests.

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
docker compose -f docker-compose.dev.yml up -d mailpit   # SMTP on 1025, web UI on http://localhost:8025
```

`docker-compose.dev.yml` sends the backend's emails there by itself. A backend run without Docker
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
cp .env.example .env     # fill in; SECRET_KEY and POSTGRES_PASSWORD e.g. with `openssl rand -hex 32`
docker compose up -d --build
```

This starts PostgreSQL, Redis and the `app` container, built by the `Dockerfile`:

- On every start, `docker/entrypoint.sh` applies the migrations first and creates or updates
  the admin user of `ADMIN_EMAIL` (`manage.py ensure_admin`).
- Then supervisord (`docker/supervisord.conf`) runs, like everything in the container, as the
  unprivileged user `app`:
  - nginx (`docker/nginx.conf`, port 8080 inside the container), which serves the built frontend and Django admin's static files
    and passes `/api`, `/admin`, `/ics`, `/caldav`, `/.well-known/caldav` and the WebSocket `/ws/`
    on;
  - uvicorn, with `WEB_WORKERS` processes;
  - the task queue's worker. It sends emails, delivers reminders, reads participants' answers
    from the iMIP mailbox (with `IMIP_ADDRESS` and the IMAP settings) and cleans up. Jobs wait in
    the database, so none is lost while it restarts.

`.env` holds the domain, the secrets, the mail settings and a few optional values; see
`.env.example`. `docker-compose.yml` derives `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and
`BASE_URL` from `DOMAIN` and sets the wiring itself: `ENVIRONMENT=production`, `DATABASE_URL`,
`REDIS_URL` and `BEHIND_PROXY=true`.

The container serves HTTP on `APP_BIND` (`127.0.0.1:6326` by default). Put a proxy in front that
terminates HTTPS, passes everything on, including WebSocket upgrades, and sets
`X-Forwarded-Proto` and `X-Forwarded-For`. Only that proxy should reach the port, because the app
trusts its forwarded headers.

The client's address is taken from `X-Forwarded-For` only when the request comes from one of
`TRUSTED_PROXIES` (default: the private networks `10.0.0.0/8`, `172.16.0.0/12`,
`192.168.0.0/16`, `fc00::/7`, which covers a proxy on the host reaching the container through
Docker's network). Failed logins are limited per client address, so a proxy elsewhere has to be
listed there, e.g. `TRUSTED_PROXIES=203.0.113.10`; `none` trusts no proxy.

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
