"""
Django settings for the Calendar backend.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# The .env of the project root, shared by all setups (template: .env.example there). In the
# containers there is none; Compose passes its values as environment variables.
load_dotenv(BASE_DIR.parent / ".env")


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list_env(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


# Production unless asked otherwise: a deployment that forgets to set it doesn't run with DEBUG,
# the development SECRET_KEY, open registration and insecure cookies.
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

_DEV_SECRET = "dev-change-me-in-production-needs-32-bytes"
SECRET_KEY = os.environ.get("SECRET_KEY", _DEV_SECRET)
if ENVIRONMENT != "development" and SECRET_KEY == _DEV_SECRET:
    raise RuntimeError(
        "SECRET_KEY must be set to a non-default value outside development"
    )

DEBUG = ENVIRONMENT == "development"

ALLOWED_HOSTS = _list_env("ALLOWED_HOSTS", ["*"])


# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # First, so that `runserver` serves the ASGI application, WebSockets included.
    "daphne",
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
    "corsheaders",
    "channels",
    # The task queue: emails, reminders and other regular jobs (core.tasks), run by
    # `manage.py procrastinate worker`.
    "procrastinate.contrib.django",
    "core",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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

# PostgreSQL only (the task queue, procrastinate, lives in it); by default the one of docker-compose.dev.yml.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://meanwhile:meanwhile@localhost:5432/meanwhile")
DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)
}


# ---------------------------------------------------------------------------
# Auth / users
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "core.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
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

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]


# ---------------------------------------------------------------------------
# allauth / headless
# ---------------------------------------------------------------------------

ACCOUNT_ADAPTER = "core.adapters.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_SIGNUP_FORM_CLASS = "core.forms.SignupForm"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_RATE_LIMITS = {
    "login_failed": "10/5m",
}

HEADLESS_ADAPTER = "core.headless_adapter.HeadlessAdapter"
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)


# ---------------------------------------------------------------------------
# Sessions / CSRF / CORS
# ---------------------------------------------------------------------------

SESSION_COOKIE_AGE = int(
    os.environ.get("SESSION_COOKIE_AGE_DAYS", "14") or "14"
) * 24 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = True

CSRF_TRUSTED_ORIGINS = _list_env(
    "CSRF_TRUSTED_ORIGINS",
    ["http://localhost:6326", "http://localhost:4173"],
)

CORS_ALLOWED_ORIGINS = _list_env(
    "CORS_ORIGINS",
    ["http://localhost:6326", "http://localhost:4173"],
)
CORS_ALLOW_CREDENTIALS = True


# ---------------------------------------------------------------------------
# Internationalization / static
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Application-specific settings
# ---------------------------------------------------------------------------

# Anyone may sign up only where that's wanted: users find each other (by name and email) to share.
ALLOW_REGISTRATION = _bool_env("ALLOW_REGISTRATION", ENVIRONMENT == "development")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
# The admin user that `manage.py ensure_admin` creates or updates on every start of the containers.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ADMIN_NAME = os.environ.get("ADMIN_NAME", "")
BASE_URL = os.environ.get("BASE_URL", "")
CALDAV_PATH = os.environ.get("CALDAV_PATH", "/caldav")


# ---------------------------------------------------------------------------
# Live updates (WebSockets) and reverse proxy
# ---------------------------------------------------------------------------

# Path of the WebSocket endpoint; the reverse proxy must pass WebSocket upgrades for it.
WEBSOCKET_PATH = os.environ.get("WEBSOCKET_PATH", "/ws/")

# Every process must reach the WebSocket connections of the others: with more than one (several
# uvicorn workers, and the task queue's worker, whose reminders pop up in the users' tabs), set
# REDIS_URL. Without it, messages stay within the process that sends them.
REDIS_URL = os.environ.get("REDIS_URL", "")
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

# Behind a reverse proxy that terminates HTTPS: trust its X-Forwarded-Proto and -Host headers.
# Only enable this when the app is reachable through the proxy alone, as clients could set them.
BEHIND_PROXY = _bool_env("BEHIND_PROXY", False)
if BEHIND_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
# Cookies only over HTTPS once the app is served that way.
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = _bool_env("SECURE_COOKIES", ENVIRONMENT != "development")


# ---------------------------------------------------------------------------
# Email (notifications and invitations)
# ---------------------------------------------------------------------------

# Without EMAIL_HOST, emails are printed to the console in development and not sent otherwise.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587") or "587")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _bool_env("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = _bool_env("EMAIL_USE_SSL", False)
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise RuntimeError("Set only one of EMAIL_USE_TLS (STARTTLS, port 587) and EMAIL_USE_SSL (port 465)")
EMAIL_TIMEOUT = 15
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
elif ENVIRONMENT == "development":
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "meanwhile@localhost")
# Emails go out as jobs of the task queue (core.tasks), retried while the mail server fails;
# without, right after the request (tests do so).
EMAIL_SEND_IN_BACKGROUND = _bool_env("EMAIL_SEND_IN_BACKGROUND", True)

# Address of the app for links in emails; BASE_URL, or in development the Vite dev server.
APP_URL = (BASE_URL or ("http://localhost:6326" if ENVIRONMENT == "development" else "")).rstrip("/")

# Forgotten passwords: allauth mails a code, which the app's page (ResetPasswordView) takes along
# with the new password, in the same browser session. A code rather than a link: allauth's link keys
# can't carry user ids with hyphens (ours are UUIDs). Only addresses with an account get one; the
# answer is the same either way, so it tells nothing.
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True
ACCOUNT_PASSWORD_RESET_BY_CODE_TIMEOUT = 15 * 60
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False

# iMIP: invitations name this mailbox as organizer, so participants' mail programs send their
# answers (iTIP REPLY) there; `fetch_imip` reads them. Empty: the organizer's own address.
IMIP_ADDRESS = os.environ.get("IMIP_ADDRESS", "")
IMIP_IMAP_HOST = os.environ.get("IMIP_IMAP_HOST", "")
IMIP_IMAP_PORT = int(os.environ.get("IMIP_IMAP_PORT", "993") or "993")
IMIP_IMAP_USER = os.environ.get("IMIP_IMAP_USER", "")
IMIP_IMAP_PASSWORD = os.environ.get("IMIP_IMAP_PASSWORD", "")
IMIP_IMAP_SSL = _bool_env("IMIP_IMAP_SSL", True)
IMIP_IMAP_FOLDER = os.environ.get("IMIP_IMAP_FOLDER", "INBOX")
# The From address of an answer is easily forged. With this set to the name the receiving mail server
# writes into its Authentication-Results header (e.g. "mx.example.com"), answers count only if that
# server found the sender's domain verified (DMARC, or DKIM signed by that domain).
IMIP_TRUSTED_AUTHSERV_ID = os.environ.get("IMIP_TRUSTED_AUTHSERV_ID", "").strip().lower()
