"""Django settings for the portfolio site.

The site is published as plain files on GitHub Pages: there is no server in
production. Django renders the pages once, at build time
("manage.py build_static"), and the result is uploaded as static files.

So Django runs in two situations only: locally, with runserver, while writing
the site; and in the build, which renders every page and exits. Nothing here
configures a running production service, because there is not one.

Content lives in content/portfolio.yaml and content/interface.yaml.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# The address the published site answers on. It goes into the canonical link,
# the hreflang links, the sitemap and the JSON-LD of every rendered page, so it
# has to be the address visitors actually reach, not the one serving the build.
SITE_URL = os.environ.get("SITE_URL", "https://viniciussilvadev.com.br").rstrip("/")
SITE_HOST = urlsplit(SITE_URL).netloc

# True while "manage.py build_static" is rendering the site to files.
STATIC_BUILD = _env_bool("DJANGO_STATIC_BUILD", False)

# Nothing secret is ever signed or stored: no sessions, no users, no forms that
# post back. The key exists because Django requires one.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "static-site-generator-not-a-secret")

DEBUG = _env_bool("DJANGO_DEBUG", not STATIC_BUILD)
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", SITE_HOST]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "portfolio",
]

MIDDLEWARE = [
    # Serves /static/ with DEBUG off: the build and the test suite both need it.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Picks the language from the address prefix (see config/urls.py).
    "django.middleware.locale.LocaleMiddleware",
    # Locally this sends the policy as a header. The published site has no
    # server to send headers, so the pages carry it in a <meta> tag built from
    # SECURE_CSP as well — one policy, two ways out.
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

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

# The site sends no e-mail; without this Django warns about the missing mailer.
MAILERS = {}
SILENCED_SYSTEM_CHECKS = ["mail.W001"]

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

# Static files. The build collects them into dist/static next to the pages;
# locally and in the tests WhiteNoise serves them straight from the app folder.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

# Everything the pages need comes from the site itself. Directives that only
# work as a header (frame-ancestors, form-action) are dropped from the <meta>
# version by portfolio.csp; GitHub Pages cannot send them.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.NONE],
    "frame-ancestors": [CSP.NONE],
}
