"""
Django settings for the Calendar backend.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


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


ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

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

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'calendar.db'}")
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
HEADLESS_FRONTEND_URLS = {}


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
    ["http://localhost:5173", "http://localhost:4173"],
)

CORS_ALLOWED_ORIGINS = _list_env(
    "CORS_ORIGINS",
    ["http://localhost:5173", "http://localhost:4173"],
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

ALLOW_REGISTRATION = _bool_env("ALLOW_REGISTRATION", True)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
BASE_URL = os.environ.get("BASE_URL", "")
CALDAV_PATH = os.environ.get("CALDAV_PATH", "/caldav")


# ---------------------------------------------------------------------------
# Live updates (WebSockets) and reverse proxy
# ---------------------------------------------------------------------------

# Path of the WebSocket endpoint; the reverse proxy must pass WebSocket upgrades for it.
WEBSOCKET_PATH = os.environ.get("WEBSOCKET_PATH", "/ws/")

# Every server process must reach the others' WebSocket connections: with more than one process
# (e.g. several uvicorn workers), set REDIS_URL. Without it, messages stay within one process,
# which is enough for development.
REDIS_URL = os.environ.get("REDIS_URL", "")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
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
