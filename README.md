# Calendar

A self-hosted calendar application with a Django backend and a Vue 3 frontend.

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
| `REDIS_URL` | - | e.g. `redis://redis:6379/0`. Required with more than one server process, so that live updates reach every process's WebSockets. Without it they stay within one process (fine for development). |
| `BEHIND_PROXY` | `false` | Trust the reverse proxy's `X-Forwarded-Proto`/`-Host`. Only when the backend is reachable through the proxy alone. |
| `SECURE_COOKIES` | `true` outside development | Session and CSRF cookies over HTTPS only. |
| `CSRF_TRUSTED_ORIGINS` | Vite dev servers | The public origin(s), e.g. `https://calendar.example.com`. |
| `WEBSOCKET_PATH` | `/ws/` | Path of the live update WebSocket. |
| `BASE_URL` | - | Public address of the app, e.g. `https://calendar.example.com`; used for feed URLs and links in emails (in development, links point to the Vite dev server). |
| `EMAIL_HOST`, `EMAIL_PORT` | -, `587` | SMTP server. Without it, emails are printed to the console in development and not sent otherwise. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | - | SMTP login. |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | `false` | STARTTLS (usually port 587) / implicit TLS (usually 465). |
| `DEFAULT_FROM_EMAIL` | `calendar@localhost` | Sender address of all emails. |
| `IMIP_ADDRESS` | - | Mailbox that receives participants' answers to invitations; invitations name it as organizer. Empty: answers go to the organizer's own address. |
| `IMIP_IMAP_HOST`, `IMIP_IMAP_PORT`, `IMIP_IMAP_USER`, `IMIP_IMAP_PASSWORD`, `IMIP_IMAP_SSL`, `IMIP_IMAP_FOLDER` | -, `993`, -, -, `true`, `INBOX` | IMAP access to that mailbox, for `fetch_imip`. |

## Authentication

The SPA uses session-cookie authentication via `django-allauth` headless browser endpoints mounted at `/api/auth/v1/auth/`. The frontend fetches a CSRF cookie from `/api/auth/csrf/` before login/register requests.

## CalDAV

CalDAV clients can connect to `/caldav`; clients that only get the server address find it via `/.well-known/caldav`. Use the email as username and either the account password or a generated app password. If any app password exists for a user, the account password is rejected for CalDAV.

Every calendar a user can access appears in their calendar home, shared ones included. Clients can create calendars there and their owners can delete them. Categories, the booked resource (as location) and participants are synchronized; each user's reminders appear as alarms in their own clients only. Times sent without a zone are read in the user's zone, which the web app keeps up to date from the browser.

## Reminders

Users set their own reminders per event. Due reminders become in-app notifications. While the app is open, the server looks for due reminders every 30 seconds over the live connection (see below) and pops them up in all of the user's tabs. To also deliver them while nobody has the app open, run this every minute, e.g. from cron:

```bash
DJANGO_SETTINGS_MODULE=config.settings uv run python manage.py send_reminders
```

## Email and invitations

Notifications can also come by email: approval requests, decisions on bookings, comments, calendar
access, participants' answers and (off by default) reminders. Each user chooses which in
*Account → Email notifications*. Emails are written in the user's language and show times in their
zone; they go out after the request in a background thread, and failures are logged.

Participants of an event are invited by email (iMIP, RFC 6047): the email carries the event as
iTIP `REQUEST`, inline and as `invite.ics`, so Thunderbird, Outlook, Apple Mail, Gmail and others
show it with their accept/decline buttons. Changes are sent as updates (with a higher `SEQUENCE`),
and deleting, cancelling or rejecting the event, or taking a participant off it, sends a `CANCEL`.
Participants without an account are reached this way too. Users with an account who switched
invitations off get them in the app only.

Participants answer either

- in their mail program: it sends an iTIP `REPLY` to the organizer address. With `IMIP_ADDRESS`
  set, that is the app's mailbox; run `fetch_imip` every few minutes to read it (IMAP). An answer
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
docker compose -f docker-compose.dev.yml up -d   # SMTP on 1025, web UI on http://localhost:8025
cp backend/.env.example backend/.env             # Mailpit is preset; a real SMTP/IMAP server is option B there
```

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

Without a working WebSocket (a proxy that doesn't pass it on), the app falls back to fetching the unread count every minute; reminders then only arrive as notifications, so keep the `send_reminders` job running.

In development nothing extra is needed: `manage.py runserver` serves WebSockets, and the Vite dev
server passes `/ws` on.

## Deployment with Docker

```bash
docker compose up --build
```

This starts PostgreSQL, Redis and the backend on port 8000 (uvicorn with `WEB_WORKERS` processes,
default 4). Set `SECRET_KEY`, and `PUBLIC_URL` to the address users open (e.g.
`https://calendar.example.com`; it becomes the trusted origin).

The backend expects a reverse proxy in front that terminates HTTPS, serves the built frontend
(`frontend/dist`) and passes `/api`, `/ics`, `/caldav`, `/.well-known/caldav` and the WebSocket
`/ws/` on. The proxy must forward WebSocket upgrades and the original host and scheme.

nginx:

```nginx
server {
    listen 443 ssl;
    server_name calendar.example.com;
    # ssl_certificate ...; ssl_certificate_key ...;

    root /srv/calendar/frontend/dist;
    location / { try_files $uri /index.html; }

    location ~ ^/(api|ics|caldav|\.well-known/caldav)(/|$) {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 10m;
    }

    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # Longer than the app's heartbeat (25 s), so idle connections stay open.
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
```

Caddy (obtains the certificate itself and passes WebSockets on as they are):

```caddy
calendar.example.com {
    @backend path /api/* /ics/* /caldav /caldav/* /.well-known/caldav /ws/*
    handle @backend {
        reverse_proxy backend:8000
    }
    # Everything else is the app; unknown paths are its routes.
    handle {
        root * /srv/calendar/frontend/dist
        try_files {path} /index.html
        file_server
    }
}
```

Only the proxy should reach port 8000 (drop the `ports:` mapping of the backend when the proxy runs
in the same Compose project); the backend trusts its forwarded headers.

To deliver reminders while nobody has the app open, run `python manage.py send_reminders` every
minute, e.g. from cron on the host via `docker compose exec backend`. With `IMIP_ADDRESS` and the
IMAP settings, also run `python manage.py fetch_imip` every few minutes to read participants'
answers to invitations.
