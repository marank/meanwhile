# Operations

How Meanwhile runs in production, for whoever hosts it. The [README](../README.md#quick-start-with-docker)
gets it started; every setting is explained in [`.env.example`](../.env.example).

## What runs

`compose.yml` and `.env` are all the server needs; no other file of the repository is mounted.
`docker compose up -d` pulls `ghcr.io/marank/meanwhile:latest` (`APP_IMAGE` pins a version, e.g.
`ghcr.io/marank/meanwhile:1.2`) and starts PostgreSQL, Redis and the image twice:

- `app`: on every start it checks the production settings (`manage.py check --deploy`), applies
  the migrations and creates or updates the admin user of `ADMIN_EMAIL`. Then nginx serves the
  app and passes `/api`, `/ics`, `/caldav`, `/.well-known/caldav` and the WebSocket `/ws/` on to
  uvicorn (`WEB_WORKERS` processes); `/django-admin` only with `ADMIN_ENABLED=true`. If one of
  them keeps failing, the container stops and Docker restarts it.
- `worker`: waits for the app's migrations, then runs the task queue. It sends emails, delivers
  reminders (every 30 seconds), reads answers to invitations from the iMIP mailbox, cleans up and
  dumps the database nightly. Jobs wait in the database, so none is lost while it restarts.

Every container but the database is hardened: read-only root filesystem, no capabilities, no
privilege escalation, unprivileged users. The app writes only to `/tmp` and `/data`, the worker
also to `/backups`. `compose.yml` sets the wiring itself: `DEBUG=false`, `DB_HOST`, `REDIS_URL`.

To check that an image was built by this repository's CI:

```bash
gh attestation verify oci://ghcr.io/marank/meanwhile:latest --owner marank
```

## Reverse proxy and TLS

The container serves HTTP on `APP_BIND` (`127.0.0.1:6326` by default). Put a proxy in front
that terminates HTTPS, passes everything on, including WebSocket upgrades, and sets
`X-Forwarded-Proto` and `X-Forwarded-For` (and keeps `Host`, or sets `X-Forwarded-Host`). The app
sends no HSTS header and doesn't redirect plain http; both are the proxy's job.

nginx in the container believes those headers only when the request comes from one of
`TRUSTED_PROXIES` (default: the private networks `10.0.0.0/8`, `172.16.0.0/12`,
`192.168.0.0/16`, `fc00::/7`, which covers a proxy on the host reaching the container through
Docker's network); from anyone else they are ignored. Failed logins are limited per client address
(by nginx, 10 per minute, and by allauth), so a proxy elsewhere has to be listed, e.g.
`TRUSTED_PROXIES=203.0.113.10`; `none` trusts no proxy.

Without a working WebSocket (a proxy that doesn't pass it on) the app still works: it fetches the
unread count every minute instead, and reminders arrive only as notifications.

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

## Email and invitations

With `EMAIL_HOST` set, Meanwhile sends notifications (each user chooses which) and invitations.
Emails are queued as jobs together with the change that caused them; while the mail server fails,
the worker tries again for about two hours. `docker compose exec app python manage.py
sendtestemail you@example.com` checks the SMTP settings.

Participants of an event get an invitation (iMIP, RFC 6047) that mail programs show with their
accept and decline buttons; changes are sent as updates, and deleting, cancelling or rejecting the
event, or taking a participant off it, sends a cancellation. Participants answer either

- with the links in the email, which always works: they open a page of the app that needs no
  account; or
- with their mail program's buttons. That answer goes to the invitation's organizer address, and
  counts only if the app can read that mailbox: set `IMIP_ADDRESS` and the `IMIP_IMAP_*` settings,
  and the worker reads it every five minutes. An answer counts only when it comes from the
  participant's own address; with `IMIP_TRUSTED_AUTHSERV_ID` only when your mail server also
  verified the sender's domain. `manage.py process_imip FILE.eml` (or `-` for standard input, e.g.
  from a mail server's pipe) applies saved messages, `manage.py fetch_imip` reads the mailbox once.

## Calendar apps and feeds

CalDAV clients connect to `/caldav`; clients that only get the server address find it via
`/.well-known/caldav`. Users sign in with their email address and an app password made in the
account settings; the app keeps only a hash of it, and revoking one locks out that client.

Each calendar also has a read-only iCal feed at `/ics/<token>.ics`. It carries no participants or
reminders, since anyone with the link can read it; the token can be renewed in the calendar
settings.

## Superusers

Superusers may sign in to the Django admin (`/django-admin/`, with `ADMIN_ENABLED=true`) and do
everything there. The app doesn't hand this out; the admin user of `ADMIN_EMAIL` is one, and others
are made (or no longer) with:

```bash
docker compose exec app python manage.py set_superuser someone@example.com
docker compose exec app python manage.py set_superuser someone@example.com --revoke
```

## Backups

The worker dumps the database every night at `BACKUP_TIME` (in `TIME_ZONE`) into the `backups`
volume and keeps `BACKUP_KEEP_DAYS` days. Dumps on the same host don't protect against losing the
host, so copy them off regularly (or point the host's backup at the volume):

```bash
docker compose exec worker python manage.py backup_database                  # a dump right now, e.g. before an update
docker compose cp worker:/backups ./backups                                   # copy all off the container
docker compose exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < file.dump   # restore
```

## Updating

`docker compose pull && docker compose up -d`. New versions may bring new settings:
`python3 scripts/sync_env.py` (from the repository) brings `.env` up to date with `.env.example`:
same order and explanations, your values unchanged, new settings added commented out (their
defaults apply until you set them), and settings that are gone listed at the end. The old file
stays as `.env.bak`; `--dry-run` only shows the changes.

Installations from before the GitHub move built the image themselves and had a `backup` service:
its old dumps stay in the `backups` volume under `backups/`; new ones go to the volume's root.
Remove the orphaned service with `docker compose up -d --remove-orphans`.
