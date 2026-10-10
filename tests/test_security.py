"""What protects the published site.

There is no server in production: the site is files on GitHub Pages. So the
protections that used to come from response headers either travel inside the
page (the content security policy) or are gone, and nothing on the page may
send data anywhere.
"""

import runpy

import pytest
from django.conf import settings

from portfolio.csp import HEADER_ONLY, meta_policy


@pytest.fixture
def load_settings(monkeypatch):
    """Evaluate config/settings.py under a given environment, without touching Django's own."""

    def load(**env):
        for name in ("SITE_URL", "DJANGO_STATIC_BUILD", "DJANGO_DEBUG", "DJANGO_SECRET_KEY"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return runpy.run_path(str(settings.BASE_DIR / "config" / "settings.py"))

    return load


def test_published_address_comes_from_the_environment(load_settings):
    built = load_settings(SITE_URL="https://exemplo.com.br/")

    assert built["SITE_URL"] == "https://exemplo.com.br"
    assert built["SITE_HOST"] == "exemplo.com.br"


def test_the_published_address_is_allowed_to_be_rendered(load_settings):
    built = load_settings(SITE_URL="https://exemplo.com.br")

    assert "exemplo.com.br" in built["ALLOWED_HOSTS"]


def test_building_the_site_turns_debug_off(load_settings):
    """A page rendered with debug on could carry settings into the published file."""
    assert load_settings(DJANGO_STATIC_BUILD="1")["DEBUG"] is False
    assert load_settings()["DEBUG"] is True


def test_policy_allows_nothing_from_outside_the_site():
    policy = meta_policy()

    assert "default-src 'self'" in policy
    assert "script-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "unsafe-inline" not in policy
    assert "unsafe-eval" not in policy


def test_policy_forbids_sending_anything_anywhere():
    """The site has no form and no server to post to; nothing should be able to try."""
    policy = meta_policy()

    assert "form-action 'none'" in policy
    assert "connect-src 'self'" in policy


def test_policy_leaves_out_directives_a_meta_tag_cannot_carry():
    """Browsers ignore them there and log a warning, so they are not written."""
    policy = meta_policy()

    assert "frame-ancestors" in settings.SECURE_CSP, "a política ainda declara a diretiva"
    assert all(directive not in policy for directive in HEADER_ONLY)


@pytest.mark.parametrize("url", ["/", "/en/", "/es/", "/404.html"])
def test_every_page_carries_the_policy(client, url):
    html = client.get(url).content.decode()

    assert '<meta http-equiv="Content-Security-Policy"' in html
    assert "default-src &#x27;self&#x27;" in html


def test_pages_have_no_form_and_nothing_to_post_to(client):
    html = client.get("/").content.decode()

    assert "<form" not in html
    assert "csrfmiddlewaretoken" not in html


def test_nothing_signs_or_stores_anything_per_visitor():
    """No sessions, no users, no database: a static site has no state to protect."""
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.dummy"
    assert "django.contrib.sessions" not in settings.INSTALLED_APPS
    assert not any("Csrf" in middleware for middleware in settings.MIDDLEWARE)
