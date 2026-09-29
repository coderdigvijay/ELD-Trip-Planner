"""Django settings. 12-factor: everything environment-specific comes from env vars.

Not env vars on purpose (docs/DEPLOYMENT.md section 1): throttle rates, cache TTLs, timeouts and
the ORS base URL. User input must never be able to choose the upstream host.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

from config.logging import build_logging_config

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")  # no-op when the file is absent (Render, CI)

# --- Mode -------------------------------------------------------------------------------------

DEBUG = env.bool("DJANGO_DEBUG", default=False)
PRODUCTION = not DEBUG

if DEBUG and env.str("RENDER", default=""):
    # A dashboard typo must never expose debug pages on Render.
    raise ImproperlyConfigured("DJANGO_DEBUG must be false when running on Render.")

# --- Secrets and required config (fail fast in production) --------------------------------------

if PRODUCTION:
    SECRET_KEY = env.str("DJANGO_SECRET_KEY")
    ORS_API_KEY = env.str("ORS_API_KEY")  # server side only; never logged or returned
    ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
    NUM_PROXIES = env.int("NUM_PROXIES")
    if NUM_PROXIES < 1:
        raise ImproperlyConfigured("NUM_PROXIES must be an integer >= 1 in production.")
else:
    SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="insecure-dev-only-key")
    ORS_API_KEY = env.str("ORS_API_KEY", default="")
    ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
    NUM_PROXIES = env.int("NUM_PROXIES", default=0)

_render_host = env.str("RENDER_EXTERNAL_HOSTNAME", default="")
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)

# --- Apps and middleware (stateless API: no DB, sessions, auth or CSRF) ------------------------

INSTALLED_APPS = [
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "rest_framework",
    "corsheaders",
    "trips",
]

MIDDLEWARE = [
    "trips.middleware.RequestContextMiddleware",  # first: every later layer and handler sees the id
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "trips.middleware.ResponseHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False  # a 301 to an HTML-less redirect is never what an API client wants

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,  # drf-spectacular's Swagger UI template only
        "OPTIONS": {"context_processors": []},
    }
]

DATABASES: dict = {}  # ADR-11: stateless
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"
USE_I18N = False

# Swagger UI assets are served by config.urls from the sidecar package.
STATIC_URL = "/api/v1/docs-assets/"

# --- Caches (LocMem; one gunicorn process shares them) ------------------------------------------

CACHES = {
    # DRF throttle counters. Separate so culling big route entries never evicts throttle state.
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eld-default",
        "OPTIONS": {"MAX_ENTRIES": 1_000},
    },
    "geo": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eld-geo",
        "OPTIONS": {"MAX_ENTRIES": 5_000},
    },
    "routes": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eld-routes",
        "OPTIONS": {"MAX_ENTRIES": 100},
    },
}

# --- Request limits -------------------------------------------------------------------------------

DATA_UPLOAD_MAX_MEMORY_SIZE = 8192

# --- DRF ------------------------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "trips.errors.exception_handler",
    "COERCE_DECIMAL_TO_STRING": False,
    "NUM_PROXIES": NUM_PROXIES,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ELD Trip Planner API",
    "DESCRIPTION": "Plans a truck trip and its FMCSA daily log sheets.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {"ErrorCode": "trips.errors.ErrorCode"},
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
}

# --- CORS (docs/DEPLOYMENT.md section 4) ------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = False
CORS_URLS_REGEX = r"^/api/v1/.*$"
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]
CORS_ALLOW_HEADERS = ["content-type"]
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Retry-After"]

# --- Security headers (production only where they would break local http) --------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "no-referrer"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
if PRODUCTION:
    # Safe only because Render's proxy overwrites X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # No includeSubDomains or preload: we do not own onrender.com.
    SECURE_HSTS_SECONDS = 31_536_000
    # Render already forces HTTPS at the edge; a redirect can fail its internal health check.
    SECURE_SSL_REDIRECT = False

# --- Logging ------------------------------------------------------------------------------------

LOGGING = build_logging_config(env.str("LOG_LEVEL", default="DEBUG" if DEBUG else "INFO"))
