import pytest


@pytest.fixture
def published(settings):
    """The site as it runs in production: one main address, reachable through two others."""
    settings.CANONICAL_HOST = "exemplo.com.br"
    settings.ALLOWED_HOSTS = ["exemplo.com.br", "www.exemplo.com.br", ".run.app"]


def test_www_is_sent_to_the_main_address(client, published):
    response = client.get("/", headers={"Host": "www.exemplo.com.br"}, secure=True)

    assert response.status_code == 301
    assert response["Location"] == "https://exemplo.com.br/"


def test_redirect_keeps_path_and_query(client, published):
    response = client.get("/en/?contato=enviado", headers={"Host": "www.exemplo.com.br"})

    assert response["Location"] == "http://exemplo.com.br/en/?contato=enviado"


def test_cloud_run_address_is_sent_to_the_main_address(client, published):
    response = client.get("/", headers={"Host": "portfolio-abc123-ue.a.run.app"}, secure=True)

    assert response.status_code == 301
    assert response["Location"] == "https://exemplo.com.br/"


def test_main_address_is_served(client, published):
    assert client.get("/", headers={"Host": "exemplo.com.br"}).status_code == 200


def test_healthz_answers_on_any_address(client, published):
    """The pipeline checks the deploy through the Cloud Run address."""
    response = client.get("/healthz", headers={"Host": "portfolio-abc123-ue.a.run.app"})

    assert response.status_code == 200


def test_without_a_main_address_every_host_is_served(client, settings):
    settings.CANONICAL_HOST = ""
    settings.ALLOWED_HOSTS = ["exemplo.com.br", "www.exemplo.com.br"]

    assert client.get("/", headers={"Host": "www.exemplo.com.br"}).status_code == 200
