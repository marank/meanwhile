"""
Django settings for the Calendar backend.
"""

from datetime import time
from pathlib import Path
from typing import Any

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

from .env import env_bool, env_int, env_list, env_str, load_dotenv, parse_app_urls, secret_key

# Lets Django's generic classes be subscripted at runtime as in their stubs (ModelAdmin[Event]).
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent

# The .env of the project root, shared by all setups (template: .env.example there); variables
# that are set already win. In the containers there is none; Compose passes its values.
load_dotenv(BASE_DIR.parent / ".env")


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

# Production unless asked otherwise: a deployment that forgets to set it doesn't run with DEBUG,
# the development SECRET_KEY, open registration and insecure cookies.
DEBUG = env_bool("DEBUG", False)
SECRET_KEY = secret_key(DEBUG)  # >= 40 chars and no placeholder, else refuse to start (DEBUG: fixed dev key)

# Every URL users open the app under. The first one is the app's address in emails and feed links.
APP_URLS = parse_app_urls(env_list("APP_URLS", ["http://localhost:6326"]))
if DEBUG:
    # Vite's dev and preview servers and runserver, so development needs no extra config.
    APP_URLS += parse_app_urls(
        ["http://localhost:6326", "http://127.0.0.1:6326", "http://localhost:4173", "http://localhost:8000"]
    )

ALLOWED_HOSTS = sorted({url.hostname for url in APP_URLS})
CSRF_TRUSTED_ORIGINS = sorted({url.origin for url in APP_URLS})

# Secure cookies only once every public URL is https (i.e. a TLS proxy is in front).
_ALL_HTTPS = not DEBUG and all(url.scheme == "https" for url in APP_URLS)
SESSION_COOKIE_SECURE = _ALL_HTTPS
CSRF_COOKIE_SECURE = _ALL_HTTPS
if _ALL_HTTPS:
    # nginx sets X-Forwarded-Proto itself and takes it over only from TRUSTED_PROXIES; the
    # backend is reachable only through nginx.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# No HSTS and no http -> https redirect from the app: the proxy in front decides that for its
# domains (the app may be served under domains that aren't ours).
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]

CSRF_COOKIE_HTTPONLY = False  # the SPA reads csrftoken to send X-CSRFToken
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# Content Security Policy for Django's own responses (admin, API); the same policy nginx sets for
# the frontend (docker/security_headers.conf) — keep the two in step. In DEBUG violations are only
# reported (browser console), as the API docs (/api/docs) load their scripts from a CDN.
_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:", "blob:"],
    "font-src": [CSP.SELF, "data:"],
    "connect-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}
if DEBUG:
    SECURE_CSP_REPORT_ONLY = _CSP
else:
    SECURE_CSP = _CSP

# The Django admin (/django-admin): on in DEBUG, off otherwise, unless ADMIN_ENABLED says differently.
ADMIN_ENABLED = env_bool("ADMIN_ENABLED", DEBUG)


# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "channels",
    # The task queue: emails, reminders and other regular jobs (apps.core.tasks), run by
    # `manage.py procrastinate worker`.
    "procrastinate.contrib.django",
    # For `manage.py export_openapi_schema` (the frontend's API types) and the docs' static files.
    "ninja",
    "apps.core",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.core.middleware.request_language",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.permissions_policy",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
# HTTP (the app, the API and the mounted CalDAV server) and WebSockets.
ASGI_APPLICATION = "config.asgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# The only writable location in the container (read-only root filesystem). Without Docker: backend/data.
DATA_DIR = Path(env_str("DATA_DIR", str(BASE_DIR / "data")))

# PostgreSQL when DB_HOST is set: in Docker (compose.yml sets it), in CI and in production. Natively
# without it, a SQLite file in DATA_DIR: no database server to start, and no task queue (below).
if env_str("DB_HOST", ""):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("DB_NAME", "meanwhile"),
            "USER": env_str("DB_USER", "meanwhile"),
            "PASSWORD": env_str("DB_PASSWORD", "meanwhile" if DEBUG else None),
            "HOST": env_str("DB_HOST"),
            "PORT": env_str("DB_PORT", "5432"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 600),
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    # Only development ends up here: production always runs with DB_HOST (compose.yml sets it).
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DATA_DIR / "db.sqlite3"}}

# Background jobs (apps/core/tasks.py, deferred through apps.core.jobs.defer): with PostgreSQL a procrastinate
# queue in the database, worked off by the worker. SQLite has no queue: jobs run in-process right
# after the transaction commits, and periodic jobs (reminders, the iMIP mailbox, backups) don't run.
JOB_QUEUE = DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
if not JOB_QUEUE:
    # The app stays installed so that apps.core.tasks can be imported (and tested with procrastinate's
    # in-memory connector); its migrations are PostgreSQL functions and are left out.
    MIGRATION_MODULES = {"procrastinate": None}

# Nightly pg_dump by the worker (apps/core/services/backups.py) into BACKUP_DIR, the "backups" volume in
# the image (/backups). Empty switches the nightly dump off.
BACKUP_DIR = env_str("BACKUP_DIR", "")
# Time of day in TIME_ZONE. Not between 02:00 and 03:00: daylight saving time skips that hour once a
# year (no backup) and repeats it once (two backups).
BACKUP_TIME = time.fromisoformat(env_str("BACKUP_TIME", "01:30"))
BACKUP_KEEP_DAYS = env_int("BACKUP_KEEP_DAYS", 14)


# ---------------------------------------------------------------------------
# Auth / users
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "core.User"

AUTHENTICATION_BACKENDS = [
    "apps.core.auth_backends.AppModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Argon2 first; the others stay as fallbacks, so existing hashes keep working.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]


# ---------------------------------------------------------------------------
# allauth / headless
# ---------------------------------------------------------------------------

ACCOUNT_ADAPTER = "apps.core.adapters.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_SIGNUP_FORM_CLASS = "apps.core.forms.SignupForm"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "none"
# Who sets a password from an emailed link (an invitation or a reset) is signed in with it right away,
# replacing whatever session the browser had: the link names the account, not who was signed in.
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_RATE_LIMITS = {
    "login_failed": "10/5m",
}

HEADLESS_ADAPTER = "apps.core.headless_adapter.HeadlessAdapter"
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

# The frontend and the backend share one origin (nginx, the Vite proxy), so there is no CORS.
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE_DAYS", 14) * 24 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = True


# ---------------------------------------------------------------------------
# Internationalization / static / logging
# ---------------------------------------------------------------------------

LANGUAGE_CODE = env_str("LANGUAGE_CODE", "en-us")
TIME_ZONE = env_str("TIME_ZONE", "UTC")
USE_I18N = True
# The languages emails are written in (each in its recipient's, apps.core.services.mail_texts); German in
# locale/de. No LocaleMiddleware: the app's language is a user setting the SPA applies itself, and
# the browser's Accept-Language must not turn the API's and allauth's messages into another one;
# the SPA names its language in X-Language instead (apps.core.middleware.request_language).
# "de-informal" addresses the reader with "du"; its catalogue (locale/de_Informal) holds only those
# texts and falls back to the formal German for the rest.
LANGUAGES = [("en", "English"), ("de", "Deutsch"), ("de-informal", "Deutsch (Du)")]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_TZ = True

# Admin assets only; nginx and Vite serve the frontend. Not "/static/", so it can't collide with
# the frontend's paths.
STATIC_URL = "/django-static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_ROOT = DATA_DIR / "media"
MEDIA_URL = "/media/"

LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "apps.core.log_filters.OffsetFormatter",
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        }
    },
    "filters": {"hide_job_arguments": {"()": "apps.core.log_filters.HideJobArguments"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default", "filters": ["hide_job_arguments"]}
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # They list every task and periodic job at each start, of every management command too.
        "procrastinate.blueprints": {"level": "WARNING"},
        "procrastinate.periodic": {"level": "WARNING"},
        # The embedded CalDAV server lists its settings at every start and logs each request (which
        # nginx's access log has too); its warnings and errors still show, everything with LOG_LEVEL=DEBUG.
        "radicale": {"level": "WARNING" if LOG_LEVEL == "INFO" else LOG_LEVEL},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Application-specific settings
# ---------------------------------------------------------------------------

# Anyone may sign up only where that's wanted: users find each other (by name and email) to share.
ALLOW_REGISTRATION = env_bool("ALLOW_REGISTRATION", DEBUG)
ADMIN_EMAIL = env_str("ADMIN_EMAIL", "")
# The admin user that `manage.py ensure_admin` creates or updates on every start of the containers.
ADMIN_PASSWORD = env_str("ADMIN_PASSWORD", "")
ADMIN_NAME = env_str("ADMIN_NAME", "")
CALDAV_PATH = env_str("CALDAV_PATH", "/caldav")
# Seconds before CalDAV answers a wrong password (Radicale's auth delay).
CALDAV_FAILED_LOGIN_DELAY = 1


# ---------------------------------------------------------------------------
# Live updates (WebSockets)
# ---------------------------------------------------------------------------

# Path of the WebSocket endpoint; the reverse proxy must pass WebSocket upgrades for it.
WEBSOCKET_PATH = env_str("WEBSOCKET_PATH", "/ws/")

# Every process must reach the WebSocket connections of the others: with more than one (several
# uvicorn workers, and the task queue's worker, whose reminders pop up in the users' tabs), set
# REDIS_URL. Without it, messages stay within the process that sends them.
REDIS_URL = env_str("REDIS_URL", "")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            # Each receive waits up to 5 s for messages (BZPOPMIN); redis-py 8 gives up reading after
            # 5 s by default, which killed every WebSocket connection after a few seconds.
            "CONFIG": {"hosts": [{"address": REDIS_URL, "socket_timeout": 30}]},
        }
    }
    # Shared by all processes, so that limits (failed logins, also CalDAV's) count across them.
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


# ---------------------------------------------------------------------------
# Email for notifications and invitations
# ---------------------------------------------------------------------------

# One mailer (Django's MAILERS; the EMAIL_* settings are deprecated since Django 6.1), configured
# from the EMAIL_* variables. Without EMAIL_HOST, emails are printed to the console in development
# and not sent otherwise.
_email_host = env_str("EMAIL_HOST", "")
_email_use_tls = env_bool("EMAIL_USE_TLS", False)
_email_use_ssl = env_bool("EMAIL_USE_SSL", False)
if _email_use_tls and _email_use_ssl:
    raise ImproperlyConfigured("Set only one of EMAIL_USE_TLS (STARTTLS, port 587) and EMAIL_USE_SSL (port 465)")
if _email_host:
    _mailer: dict[str, Any] = {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": _email_host,
            "port": env_int("EMAIL_PORT", 587),
            "username": env_str("EMAIL_HOST_USER", ""),
            "password": env_str("EMAIL_HOST_PASSWORD", ""),
            "use_tls": _email_use_tls,
            "use_ssl": _email_use_ssl,
            "timeout": 15,
        },
    }
elif DEBUG:
    _mailer = {"BACKEND": "django.core.mail.backends.console.EmailBackend"}
else:
    _mailer = {"BACKEND": "django.core.mail.backends.dummy.EmailBackend"}
    # Running without a mail server is allowed (.env.example); the deploy check at start must not refuse it.
    SILENCED_SYSTEM_CHECKS.append("mail.E001")
MAILERS = {"default": _mailer}
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "meanwhile@localhost")
# Emails go out as jobs of the task queue (apps.core.tasks), retried while the mail server fails;
# without, right after the request (tests do so).
EMAIL_SEND_IN_BACKGROUND = env_bool("EMAIL_SEND_IN_BACKGROUND", True)

# Address of the app for links in emails and feed URLs: the first of APP_URLS.
APP_URL = APP_URLS[0].origin

# Forgotten passwords: allauth mails a link to the app's page that sets a new one (ResetPasswordView);
# the key in it works once, for PASSWORD_RESET_TIMEOUT. Only addresses with an account get one; the
# answer is the same either way, so it tells nothing.
HEADLESS_FRONTEND_URLS = {"account_reset_password_from_key": f"{APP_URL}/reset-password/{{key}}"}
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False

# iMIP: invitations name this mailbox as organizer, so participants' mail programs send their
# answers (iTIP REPLY) there; `fetch_imip` reads them. Empty: the organizer's own address.
IMIP_ADDRESS = env_str("IMIP_ADDRESS", "")
IMIP_IMAP_HOST = env_str("IMIP_IMAP_HOST", "")
IMIP_IMAP_PORT = env_int("IMIP_IMAP_PORT", 993)
IMIP_IMAP_USER = env_str("IMIP_IMAP_USER", "")
IMIP_IMAP_PASSWORD = env_str("IMIP_IMAP_PASSWORD", "")
IMIP_IMAP_SSL = env_bool("IMIP_IMAP_SSL", True)
IMIP_IMAP_FOLDER = env_str("IMIP_IMAP_FOLDER", "INBOX")
# The From address of an answer is easily forged. With this set to the name the receiving mail server
# writes into its Authentication-Results header (e.g. "mx.example.com"), answers count only if that
# server found the sender's domain verified (DMARC, or DKIM signed by that domain).
IMIP_TRUSTED_AUTHSERV_ID = env_str("IMIP_TRUSTED_AUTHSERV_ID", "").strip().lower()
