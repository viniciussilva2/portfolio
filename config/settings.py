"""Django settings for the portfolio site.

Stateless by design: no database, no sessions, no admin. Content lives in
content/portfolio.yaml. DJANGO_ENV=production (baked into the Docker image)
turns on strict mode; anything else is local development.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


IS_PRODUCTION = os.environ.get("DJANGO_ENV", "development") == "production"
DEBUG = not IS_PRODUCTION

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DJANGO_ENV=production.")
    SECRET_KEY = "dev-only-key-never-used-in-production"

ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS", "" if IS_PRODUCTION else "localhost,127.0.0.1,[::1]"
)
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
# The one address the site is known by; every other allowed host redirects to
# it. Empty means no redirect: development, and production before the domain.
CANONICAL_HOST = os.environ.get("DJANGO_CANONICAL_HOST", "").strip()

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "portfolio",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "portfolio.middleware.CanonicalHostMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

DATABASES = {}

# Portuguese at "/", English at "/en/", Spanish at "/es/". The language comes
# from the address only: "/" is Portuguese whatever the browser prefers.
LANGUAGE_CODE = "pt-br"
LANGUAGES = [("pt-br", "Português"), ("en", "English"), ("es", "Español")]
TIME_ZONE = "America/Bahia"
USE_I18N = True
USE_TZ = True

# Content: the person, and the interface texts, each in the three languages.
CONTENT_FILE = BASE_DIR / "content" / "portfolio.yaml"
INTERFACE_FILE = BASE_DIR / "content" / "interface.yaml"

# Static files (served by WhiteNoise; hashed + compressed in production)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Outside production there is no collectstatic: serve straight from the app folders.
WHITENOISE_USE_FINDERS = not IS_PRODUCTION
WHITENOISE_AUTOREFRESH = not IS_PRODUCTION
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# Contact form e-mail. In development, without EMAIL_HOST, messages are printed
# to the console. In production there is no console anyone reads: without a
# mail server the form is taken off the page, rather than telling visitors
# "sent" for messages that go nowhere.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
CONTACT_FORM_ENABLED = bool(EMAIL_HOST) or not IS_PRODUCTION
if not CONTACT_FORM_ENABLED:
    MAILERS = {}
elif EMAIL_HOST:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": EMAIL_HOST,
                "port": int(os.environ.get("EMAIL_PORT", "587")),
                "username": os.environ.get("EMAIL_HOST_USER", ""),
                "password": os.environ.get("EMAIL_HOST_PASSWORD", ""),
                "use_tls": _env_bool("EMAIL_USE_TLS", True),
                "timeout": 10,
            },
        },
    }
else:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
del EMAIL_HOST
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Portfolio <contato@localhost>")
CONTACT_TO_EMAIL = os.environ.get("CONTACT_TO_EMAIL", "contato@localhost")

# Contact form anti-spam
CONTACT_MIN_FILL_SECONDS = 3
CONTACT_MAX_FORM_AGE_SECONDS = 60 * 60 * 6
CONTACT_RATE_LIMIT = 5
CONTACT_RATE_WINDOW_SECONDS = 60 * 60

# Security. Cloud Run terminates TLS and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
HTTPS_ONLY = _env_bool("DJANGO_HTTPS_ONLY", IS_PRODUCTION)
SECURE_SSL_REDIRECT = HTTPS_ONLY
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365 if HTTPS_ONLY else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS_ONLY
CSRF_COOKIE_SECURE = HTTPS_ONLY
# HSTS preload is a hard-to-reverse commitment for the whole domain; opt in deliberately.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
if not CONTACT_FORM_ENABLED:
    # No mailer on purpose: with the form off, nothing sends e-mail.
    SILENCED_SYSTEM_CHECKS.append("mail.W001")

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}

# Cloud Run collects stdout/stderr; Django's default hides errors when DEBUG is off.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
