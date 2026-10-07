import smtplib
import time

import pytest
from django.core import mail
from django.core.cache import cache
from django.core.mail.backends.base import BaseEmailBackend
from django.test import Client

from portfolio.forms import new_form_token

JSON = {"headers": {"Accept": "application/json"}}


class FailingBackend(BaseEmailBackend):
    """Stands in for an SMTP server that is down."""

    def send_messages(self, email_messages):
        raise smtplib.SMTPException("servidor indisponível")


@pytest.fixture(autouse=True)
def clean_rate_limit():
    cache.clear()
    yield
    cache.clear()


def filled_form(**overrides):
    """A message from a real visitor who took ten seconds to write it."""
    data = {
        "name": "Maria Recrutadora",
        "email": "maria@empresa.com.br",
        "message": "Olá, Vinicius. Temos uma vaga de analista de sistemas e gostaria de conversar.",
        "website": "",
        "token": new_form_token(issued_at=time.time() - 10),
    }
    data.update(overrides)
    return data


def test_valid_message_is_emailed_to_the_site_owner(client, settings):
    settings.CONTACT_TO_EMAIL = "dono@exemplo.com.br"

    response = client.post("/contato", filled_form(), **JSON)

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == ["dono@exemplo.com.br"]
    assert "Maria Recrutadora" in sent.subject
    assert "Temos uma vaga de analista de sistemas" in sent.body
    assert "maria@empresa.com.br" in sent.body


def test_reply_goes_to_the_visitor(client):
    client.post("/contato", filled_form(), **JSON)

    assert mail.outbox[0].reply_to == ["maria@empresa.com.br"]


def test_success_tells_the_visitor_the_message_was_sent(client):
    response = client.post("/contato", filled_form(), **JSON)

    assert response.json()["message"] == "Mensagem enviada. Respondo pelo e-mail informado."


def test_without_javascript_success_redirects_back_to_contact_section(client):
    response = client.post("/contato", filled_form())

    assert response.status_code == 302
    assert response["Location"] == "/?contato=enviado#contato"


def test_home_confirms_delivery_after_redirect(client):
    html = client.get("/?contato=enviado").content.decode()

    assert "Mensagem enviada. Respondo pelo e-mail informado." in html


def test_home_does_not_confirm_delivery_on_a_normal_visit(client):
    html = client.get("/").content.decode()

    assert "Mensagem enviada." not in html


def test_empty_form_reports_each_missing_field_and_sends_nothing(client):
    response = client.post("/contato", filled_form(name="", email="", message=""), **JSON)

    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["errors"]["name"] == ["Informe seu nome."]
    assert body["errors"]["email"] == ["Informe seu e-mail."]
    assert body["errors"]["message"] == ["Escreva a mensagem."]
    assert mail.outbox == []


def test_invalid_email_is_rejected(client):
    response = client.post("/contato", filled_form(email="maria-sem-arroba"), **JSON)

    assert response.status_code == 400
    assert response.json()["errors"]["email"] == ["Informe um e-mail válido."]
    assert mail.outbox == []


def test_without_javascript_errors_are_shown_on_the_page_with_typed_values_kept(client):
    response = client.post("/contato", filled_form(email="maria-sem-arroba"))
    html = response.content.decode()

    assert response.status_code == 400
    assert "Informe um e-mail válido." in html
    assert 'value="Maria Recrutadora"' in html


def test_bot_that_fills_the_hidden_field_gets_fake_success_and_no_email(client):
    response = client.post("/contato", filled_form(website="http://spam.example"), **JSON)

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert mail.outbox == []


def test_form_submitted_faster_than_a_person_can_type_is_rejected(client):
    instant = new_form_token(issued_at=time.time())

    response = client.post("/contato", filled_form(token=instant), **JSON)

    assert response.status_code == 400
    assert "Aguarde alguns segundos" in response.json()["error"]
    assert mail.outbox == []


def test_forged_token_is_rejected(client):
    response = client.post("/contato", filled_form(token="forjado"), **JSON)

    assert response.status_code == 400
    assert mail.outbox == []


def test_expired_form_asks_to_send_again_and_hands_out_a_fresh_token(client, settings):
    stale = new_form_token(issued_at=time.time() - settings.CONTACT_MAX_FORM_AGE_SECONDS - 60)

    response = client.post("/contato", filled_form(token=stale), **JSON)

    body = response.json()
    assert response.status_code == 400
    assert "expirou" in body["error"]
    assert body["token"] not in ("", stale)
    assert mail.outbox == []


def test_messages_beyond_the_hourly_limit_are_refused(client, settings):
    settings.CONTACT_RATE_LIMIT = 2

    first = client.post("/contato", filled_form(), **JSON)
    second = client.post("/contato", filled_form(), **JSON)
    third = client.post("/contato", filled_form(), **JSON)

    assert (first.status_code, second.status_code, third.status_code) == (200, 200, 429)
    assert "Muitas mensagens" in third.json()["error"]
    assert len(mail.outbox) == 2


def test_rate_limit_is_counted_per_visitor_address(client, settings):
    settings.CONTACT_RATE_LIMIT = 1

    client.post("/contato", filled_form(), REMOTE_ADDR="203.0.113.10", **JSON)
    other = client.post("/contato", filled_form(), REMOTE_ADDR="203.0.113.20", **JSON)

    assert other.status_code == 200


def test_rate_limit_ignores_forwarded_addresses_the_client_made_up(client, settings):
    """The proxy appends the real address last; earlier entries are client-supplied."""
    settings.CONTACT_RATE_LIMIT = 1

    def post(spoofed):
        headers = {"Accept": "application/json", "X-Forwarded-For": f"{spoofed}, 203.0.113.10"}
        return client.post("/contato", filled_form(), headers=headers)

    assert post("10.0.0.1").status_code == 200
    assert post("10.0.0.2").status_code == 429


def test_line_breaks_in_name_cannot_inject_email_headers(client):
    response = client.post("/contato", filled_form(name="Maria\r\nBcc: vitima@exemplo.com"), **JSON)

    assert response.status_code == 200
    assert "\n" not in mail.outbox[0].subject
    assert mail.outbox[0].bcc == []


def test_mail_server_failure_is_reported_instead_of_pretending_success(client, settings):
    settings.MAILERS = {"default": {"BACKEND": "tests.test_contact.FailingBackend"}}

    response = client.post("/contato", filled_form(), **JSON)

    assert response.status_code == 502
    assert response.json()["ok"] is False
    assert "Não foi possível enviar" in response.json()["error"]


def test_page_has_no_form_when_the_contact_form_is_off(client, settings):
    settings.CONTACT_FORM_ENABLED = False

    html = client.get("/").content.decode()

    assert "<form" not in html
    assert "Para vagas, projetos ou dúvidas técnicas, use um dos canais abaixo." in html
    assert 'href="https://www.linkedin.com/in/' in html


def test_messages_are_refused_when_the_contact_form_is_off(client, settings):
    settings.CONTACT_FORM_ENABLED = False

    response = client.post("/contato", filled_form(), **JSON)

    assert response.status_code == 404
    assert mail.outbox == []


def test_contact_endpoint_only_accepts_post(client):
    assert client.get("/contato").status_code == 405


def test_post_without_csrf_token_is_refused():
    strict = Client(enforce_csrf_checks=True)

    assert strict.post("/contato", filled_form(), **JSON).status_code == 403
