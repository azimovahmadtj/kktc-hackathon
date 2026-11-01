"""
Django settings for Otel İş Portalı.

Configuration comes from environment variables, or from a `.env` file in the
project root (copy `.env.example` to `.env`).

    DATABASE_URL        optional; empty = SQLite file db.sqlite3 (built into Python)
                        postgres://USER:PASSWORD@HOST:5432/DBNAME for PostgreSQL
    ANTHROPIC_API_KEY   enables the AI CV matching
    DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS
"""
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Minimal .env reader (KEY=VALUE lines). Real environment variables win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
# In development (DEBUG) the site also opens from a phone on the same Wi-Fi (http://192.168.x.x:8000)
# and through tunnels (cloudflared / ngrok). In production set DJANGO_ALLOWED_HOSTS explicitly.
_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(",") if h.strip()] if _hosts else (
    ["*"] if DEBUG else ["localhost", "127.0.0.1"])
_origins = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()] if _origins else (
    ["https://*.trycloudflare.com", "https://*.ngrok-free.app", "https://*.ngrok.app"] if DEBUG else [])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "otelportal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "portal.context_processors.portal",
            ],
        },
    },
]

WSGI_APPLICATION = "otelportal.wsgi.application"

# ---- Database ----
# Default: SQLite (built into Python, nothing to install) -> db.sqlite3 in the project folder.
# Set DATABASE_URL=postgres://... to use PostgreSQL instead.


def _database_from_url(url):
    parsed = urlparse(url)
    if parsed.scheme == "sqlite":
        # sqlite:///db.sqlite3 (relative to the project) or sqlite:////absolute/path.sqlite3
        name = unquote(parsed.path[1:] if parsed.path.startswith("/") else parsed.path) or "db.sqlite3"
        path = Path(name)
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": path if path.is_absolute() else BASE_DIR / path}
    if parsed.scheme in ("postgres", "postgresql"):
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "127.0.0.1",
            "PORT": str(parsed.port or 5432),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
        }
    raise ImproperlyConfigured("DATABASE_URL must start with sqlite:// or postgres:// (got %r)" % parsed.scheme)


_database_url = os.environ.get("DATABASE_URL", "").strip()
DATABASES = {
    "default": _database_from_url(_database_url) if _database_url
    else {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

AUTH_USER_MODEL = "portal.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "landing"

# ---- Languages: only Turkish, English and Russian ----
LANGUAGE_CODE = "tr"
LANGUAGES = [
    ("tr", _("Turkish")),
    ("en", _("English")),
    ("ru", _("Russian")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "oip_language"
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
USE_I18N = True

TIME_ZONE = "Asia/Famagusta"  # Northern Cyprus
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded CVs. They are NOT exposed under a public URL; views check permissions before serving.
MEDIA_ROOT = BASE_DIR / "media"
CV_MAX_UPLOAD_BYTES = 5 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- AI CV matching (Claude API) ----
# Without ANTHROPIC_API_KEY the feature is shown as "not configured"; everything else works.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
AI_MAX_JOBS_IN_PROMPT = int(os.environ.get("AI_MAX_JOBS_IN_PROMPT", "150"))
AI_TIMEOUT_SECONDS = float(os.environ.get("AI_TIMEOUT_SECONDS", "120"))

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
