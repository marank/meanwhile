# Contributing to Meanwhile

Thanks for helping. Bug reports and ideas are welcome as issues.

> [!IMPORTANT]
> Meanwhile is still in active development, so pull requests are not accepted for now; they are
> closed without review. The steps below describe how it will work once that changes.

## Issues

Use the issue forms: **Bug report** (what you did, what you expected, what happened, the
version) or **Feature request** (the problem first, then the idea). Remove personal data
from logs and screenshots. **Security issues** never go into a public issue — see
[SECURITY.md](SECURITY.md).

## Pull requests

1. Discuss larger changes in an issue first.
2. Fork, branch from `main`, keep the change focused on one topic.
3. Set up the project as described under [Development](#development).
4. Follow the conventions in [AGENTS.md](AGENTS.md): structure, services, UUID models,
   strict typing, English and German texts, no inline scripts.
5. Add or update tests; coverage must stay at or above the minimums (backend 90 %,
   frontend 95/95/95/90 lines/statements/functions/branches).
6. After model changes run `just migrations`, after API changes `just api-types`, and
   commit the generated files.
7. Update the documentation when users or operators notice the change.
8. Run `just check` before you push; CI runs the same recipes on the pull request.

## Development

Prerequisites: [uv](https://docs.astral.sh/uv/), Node.js 24 with pnpm (`npm install -g pnpm`),
just ≥ 1.42 (`uv tool install rust-just`, `winget install Casey.Just` or `brew install just`),
and GNU gettext for the translation checks (`winget install mlocati.GetText`,
`brew install gettext`, `apt install gettext`). Docker only for the image and the optional services.

```bash
cp .env.example .env     # once, in the project root; then set DEBUG=true (ADMIN_* give you a user to sign in with)
just setup               # uv sync + pnpm install
just dev                 # Django on :8000 and Vite on http://localhost:6326; Ctrl+C stops both
```

`just dev` runs `just dev-backend` (migrations, admin user, Django with SQLite in backend/data)
and `just dev-frontend` side by side in one terminal; start them separately to keep their output
apart. In VS Code the task `dev` starts both, each in its own panel; every task only calls a just
recipe (`just` lists them).
The Vite dev proxy forwards `/api`, `/django-admin`, `/django-static`, `/ics`, `/caldav` and `/ws`
to `http://localhost:8000`, keeping the browser's `Host`.

Natively there is no database server and no worker: the backend uses SQLite, and jobs (emails)
run right after the request's transaction. Periodic jobs (reminders, iMIP answers, clean-ups,
backups) don't run. To run like CI and production, start PostgreSQL, Redis and Mailpit, then the
worker:

```bash
just services           # compose.dev.yml; then in .env: DB_HOST=localhost, DB_PASSWORD=meanwhile, REDIS_URL=redis://localhost:6379/0
just dev-worker         # the task queue's worker (apps/core/tasks.py)
```

Without `DEBUG=true` the backend runs as in production: it refuses to start without a real
`SECRET_KEY`. The tests always use development settings (`config/settings_test.py`) and run in
parallel; `uv run pytest -n 0` (in `backend/`) runs them in one process, e.g. to debug with `-s`
or `--pdb`. Natively they run on SQLite, with `DB_HOST` on PostgreSQL like CI.

| Command | When |
| --- | --- |
| `just check` | Before every push: exactly what CI runs (backend, deploy settings, frontend, workflows) |
| `just api-types` | After API changes: schema → `frontend/openapi.json` → `src/api/schema.d.ts`; commit both |
| `just migrations` | After model changes; commit the migrations |
| `just messages` | After new backend texts; translate `backend/locale/de/LC_MESSAGES/django.po` |
| `just sync-env` | After pulling: adds new entries of `.env.example` to `.env` |
| `just check-eol` | Whether Python, Debian, Node.js, PostgreSQL or Django lose support within 180 days (CI runs it weekly) |

In `frontend/`: `pnpm test:unit` (Vitest), `pnpm lint` (oxlint, ESLint, knip), `pnpm lint:fix`,
`pnpm format` (Prettier), `pnpm type-check` (vue-tsc). Fast checks before each commit:
`uv tool run pre-commit install` once. Locally made superusers: `uv run python manage.py
set_superuser someone@example.com` in `backend/`.

### Testing emails

[Mailpit](https://mailpit.axllent.org/) (started by `just services`) catches every email: SMTP on
1025, web UI on http://localhost:8025. Set `EMAIL_HOST=localhost`, `EMAIL_PORT=1025`,
`EMAIL_USE_TLS=false` and `IMIP_ADDRESS=meanwhile@localhost` in `.env` and restart the backend;
invitations' links then lead to the Vite dev server. To test answers from mail programs:

```bash
cd backend
uv run python manage.py imip_reply <event-id> guest@example.com accepted   # sends an iTIP REPLY to IMIP_ADDRESS
uv run python manage.py fetch_imip --mailpit http://localhost:8025         # reads unread answers from Mailpit
```

`imip_reply --process` applies the answer right away, without a mailbox. Without `EMAIL_HOST`,
emails are printed to the backend's console.

## Commits and releases

Pull requests are squash-merged, and their title becomes the commit on `main`. Write it as a
[Conventional Commit](https://www.conventionalcommits.org/) in English: `feat: show the owner
on the detail page`, `fix: …`, `docs: …`, `chore: …`; `feat!:` or a `BREAKING CHANGE:` footer
for incompatible changes. Releases are made from these titles (CHANGELOG.md, version number),
so they describe the change for users.

release-please (`.github/workflows/release.yaml`) keeps a release pull request up to date with
CHANGELOG.md and the next version; merging it tags `vX.Y.Z` and pushes the image as `X.Y.Z`,
`X.Y` and `X`. Dependabot titles updates that reach the image `deps:` (listed under
"Dependencies") and development tools `chore(deps):`.

`.github/workflows/build.yaml` runs `just check-backend` (on PostgreSQL), `check-deploy`,
`check-frontend` and `check-workflows`, scans the repository (Trivy), then builds the image on
amd64 and arm64, smoke-tests app and worker hardened against a throwaway PostgreSQL
(`docker/smoke-test`), scans it and pushes one multi-platform image with a provenance
attestation (`latest` and `sha-…` from `main`). `main` is rebuilt weekly for Debian's security
fixes; the weekly run also checks the platforms' end of support (`just check-eol`).

Set up once on GitHub:

1. **Ruleset for `main`**: pull requests required, squash merge only (PR title as commit message),
   required status checks `backend`, `frontend`, `workflows`, `repository`, both `image` jobs and
   `dependency-review` (not `eol`).
2. **Actions → General**: allow GitHub Actions to create and approve pull requests (release-please).
3. **Advanced Security**: private vulnerability reporting, Dependabot alerts, secret scanning with
   push protection, CodeQL default setup.
4. **Releases**: immutable releases on.
5. **Package**: after the first push, make `ghcr.io/marank/meanwhile` public and link it to the
   repository.

## License

Meanwhile is licensed under the [AGPL-3.0-or-later](LICENSE). By submitting a contribution
you agree that it is licensed under the same terms. Dependencies must be compatible with
it (checked in CI).
