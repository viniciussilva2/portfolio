import runpy

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

ENV_VARS = (
    "DJANGO_ENV",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_HTTPS_ONLY",
    "DJANGO_CANONICAL_HOST",
    "EMAIL_HOST",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
)


@pytest.fixture
def load_settings(monkeypatch):
    """Evaluate config/settings.py under a given environment, without touching Django's own."""

    def load(**env):
        for name in ENV_VARS:
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return runpy.run_path(str(settings.BASE_DIR / "config" / "settings.py"))

    return load


def test_production_refuses_to_start_without_secret_key(load_settings):
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        load_settings(DJANGO_ENV="production")


def test_production_disables_debug_and_forces_https(load_settings):
    prod = load_settings(DJANGO_ENV="production", DJANGO_SECRET_KEY="x" * 60)

    assert prod["DEBUG"] is False
    assert prod["SECURE_SSL_REDIRECT"] is True
    assert prod["SECURE_HSTS_SECONDS"] >= 31536000
    assert prod["CSRF_COOKIE_SECURE"] is True


def test_production_only_serves_configured_hosts(load_settings):
    prod = load_settings(
        DJANGO_ENV="production",
        DJANGO_SECRET_KEY="x" * 60,
        DJANGO_ALLOWED_HOSTS="exemplo.com.br, www.exemplo.com.br",
    )

    assert prod["ALLOWED_HOSTS"] == ["exemplo.com.br", "www.exemplo.com.br"]


def test_main_address_comes_from_the_environment(load_settings):
    prod = load_settings(
        DJANGO_ENV="production",
        DJANGO_SECRET_KEY="x" * 60,
        DJANGO_CANONICAL_HOST=" exemplo.com.br ",
    )

    assert prod["CANONICAL_HOST"] == "exemplo.com.br"


def test_there_is_no_main_address_unless_one_is_set(load_settings):
    assert load_settings()["CANONICAL_HOST"] == ""


def test_production_serves_hashed_static_files(load_settings):
    prod = load_settings(DJANGO_ENV="production", DJANGO_SECRET_KEY="x" * 60)

    assert "Manifest" in prod["STORAGES"]["staticfiles"]["BACKEND"]


def test_production_can_run_over_plain_http_for_local_container(load_settings):
    local = load_settings(
        DJANGO_ENV="production", DJANGO_SECRET_KEY="x" * 60, DJANGO_HTTPS_ONLY="false"
    )

    assert local["SECURE_SSL_REDIRECT"] is False
    assert local["CSRF_COOKIE_SECURE"] is False


def test_development_does_not_force_https(load_settings):
    dev = load_settings()

    assert dev["DEBUG"] is True
    assert dev["SECURE_SSL_REDIRECT"] is False


def test_mail_goes_to_console_without_smtp_host(load_settings):
    dev = load_settings()

    assert dev["MAILERS"]["default"]["BACKEND"].endswith("console.EmailBackend")
    assert dev["CONTACT_FORM_ENABLED"] is True


def test_production_without_a_mail_server_turns_the_contact_form_off(load_settings):
    """Otherwise visitors would be told "sent" while the message went nowhere."""
    prod = load_settings(DJANGO_ENV="production", DJANGO_SECRET_KEY="x" * 60)

    assert prod["CONTACT_FORM_ENABLED"] is False
    assert prod["MAILERS"] == {}


def test_production_with_a_mail_server_keeps_the_contact_form(load_settings):
    prod = load_settings(
        DJANGO_ENV="production", DJANGO_SECRET_KEY="x" * 60, EMAIL_HOST="smtp.exemplo.com"
    )

    assert prod["CONTACT_FORM_ENABLED"] is True


def test_mail_uses_smtp_credentials_when_host_is_set(load_settings):
    prod = load_settings(
        DJANGO_ENV="production",
        DJANGO_SECRET_KEY="x" * 60,
        EMAIL_HOST="smtp.exemplo.com",
        EMAIL_HOST_USER="usuario",
        EMAIL_HOST_PASSWORD="segredo",
    )
    mailer = prod["MAILERS"]["default"]

    assert mailer["BACKEND"].endswith("smtp.EmailBackend")
    assert mailer["OPTIONS"]["host"] == "smtp.exemplo.com"
    assert mailer["OPTIONS"]["username"] == "usuario"
    assert mailer["OPTIONS"]["password"] == "segredo"
    assert mailer["OPTIONS"]["use_tls"] is True


def test_home_sends_strict_content_security_policy(client):
    policy = client.get("/")["Content-Security-Policy"]

    assert "default-src 'self'" in policy
    assert "script-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy


def test_home_forbids_framing(client):
    assert client.get("/")["X-Frame-Options"] == "DENY"


def test_https_redirect_applies_to_pages(client, settings):  # noqa: F811
    settings.SECURE_SSL_REDIRECT = True

    response = client.get("/")

    assert response.status_code == 301
    assert response["Location"] == "https://testserver/"


def test_healthz_is_exempt_from_https_redirect(client, settings):  # noqa: F811
    settings.SECURE_SSL_REDIRECT = True

    assert client.get("/healthz").status_code == 200
