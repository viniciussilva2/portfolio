"""The site in Portuguese (default), English and Spanish."""

import copy
import datetime as dt
import re
import time
from pathlib import Path

import pytest
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.utils import translation
from django.utils.html import escape

from portfolio.content import (
    LANGUAGES,
    ContentError,
    format_duration,
    get_content,
    get_interface,
    load_content,
    load_interface,
    parse_content,
)
from portfolio.forms import new_form_token
from tests.test_content import VALID

JSON = {"headers": {"Accept": "application/json"}}


@pytest.fixture(autouse=True)
def clean_rate_limit():
    cache.clear()
    yield
    cache.clear()


def translated_data():
    data = copy.deepcopy(VALID)
    data["profile"]["role"] = {
        "pt": "Analista de Sistemas",
        "en": "Systems Analyst",
        "es": "Analista de Sistemas (es)",
    }
    data["profile"]["about"] = {
        "pt": ["Primeiro parágrafo."],
        "en": ["First paragraph."],
        "es": ["Primer párrafo."],
    }
    data["experiences"][1]["highlights"] = [
        {"pt": "Criou API", "en": "Built an API", "es": "Creó una API"}
    ]
    return data


# Content file


def test_translated_text_resolves_to_the_requested_language():
    assert parse_content(translated_data(), "en").profile.role == "Systems Analyst"
    assert parse_content(translated_data(), "es").profile.role == "Analista de Sistemas (es)"


def test_portuguese_is_the_language_when_none_is_requested():
    assert parse_content(translated_data()).profile.role == "Analista de Sistemas"


def test_a_whole_list_can_be_translated():
    assert parse_content(translated_data(), "en").profile.about == ("First paragraph.",)


def test_items_inside_a_list_can_be_translated_one_by_one():
    english = parse_content(translated_data(), "en")

    assert english.experiences[1].highlights == ("Built an API",)


def test_plain_text_is_the_same_in_every_language():
    assert parse_content(translated_data(), "es").profile.name == "Fulano de Tal"


def test_missing_translation_is_rejected_naming_field_and_language():
    data = translated_data()
    del data["profile"]["role"]["es"]

    with pytest.raises(ContentError, match=r"profile\.role.*'es'"):
        parse_content(data, "pt")


def test_translation_for_a_language_the_site_does_not_have_is_rejected():
    data = translated_data()
    data["profile"]["role"]["fr"] = "Analyste"

    with pytest.raises(ContentError, match=r"profile\.role.*'fr'"):
        parse_content(data, "pt")


@pytest.mark.parametrize("language", LANGUAGES)
def test_published_content_is_valid_in_every_language(language):
    content = load_content(settings.CONTENT_FILE, language)

    assert len(content.experiences) == 6
    assert content.ai.tools


def test_published_content_is_actually_translated():
    roles = {load_content(settings.CONTENT_FILE, language).profile.role for language in LANGUAGES}
    summaries = {
        load_content(settings.CONTENT_FILE, language).experiences[0].summary
        for language in LANGUAGES
    }

    assert "Systems Analyst" in roles
    assert len(summaries) == 3


# Dates and durations


@pytest.mark.parametrize(
    ("language", "period"),
    [
        ("pt-br", "mai/2026 – atual"),
        ("en", "May 2026 – present"),
        ("es", "may 2026 – actualidad"),
    ],
)
def test_current_job_period_follows_the_active_language(language, period):
    current = parse_content(copy.deepcopy(VALID)).experiences[0]

    with translation.override(language):
        assert current.period == period


@pytest.mark.parametrize(
    ("language", "months", "label"),
    [
        ("en", 1, "1 month"),
        ("en", 18, "1 year and 6 months"),
        ("en", 25, "2 years and 1 month"),
        ("es", 1, "1 mes"),
        ("es", 18, "1 año y 6 meses"),
        ("es", 24, "2 años"),
    ],
)
def test_duration_follows_the_active_language(language, months, label):
    with translation.override(language):
        assert format_duration(months) == label


def test_job_duration_follows_the_active_language():
    past = parse_content(copy.deepcopy(VALID)).experiences[1]

    with translation.override("en"):
        assert past.duration_at(dt.date(2030, 1, 1)) == "1 year and 6 months"


def test_content_follows_the_active_language():
    with translation.override("en"):
        assert get_content().profile.role == "Systems Analyst"
    with translation.override("es"):
        assert get_content().experiences[0].period.endswith("actualidad")


# Interface texts (menus, buttons, form)


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_interface_text_exists_in_every_language(language):
    texts = load_interface(settings.INTERFACE_FILE, language)

    assert texts
    assert all(isinstance(text, str) and text for text in texts.values())


def test_interface_text_without_a_translation_is_rejected(tmp_path):
    broken = tmp_path / "interface.yaml"
    broken.write_text("nav_about:\n  pt: Sobre\n  en: About\n", encoding="utf-8")

    with pytest.raises(ContentError, match=r"nav_about.*'es'"):
        load_interface(broken, "pt")


def test_templates_and_code_only_use_interface_texts_that_exist():
    app = Path(settings.BASE_DIR) / "portfolio"
    used = set()
    for template in (app / "templates").rglob("*.html"):
        used.update(re.findall(r"\bui\.([a-z_]+)", template.read_text(encoding="utf-8")))
    for module in app.glob("*.py"):
        used.update(re.findall(r'ui\["([a-z_]+)"\]', module.read_text(encoding="utf-8")))

    assert used, "nenhum texto de interface encontrado"
    assert sorted(used - set(get_interface())) == []


# Pages


def html_of(client, url, **extra):
    response = client.get(url, **extra)
    assert response.status_code == 200
    return response.content.decode()


def test_home_is_portuguese_by_default(client):
    html = html_of(client, "/")

    assert '<html lang="pt-BR">' in html
    assert ">Experiência<" in html


def test_home_stays_portuguese_even_when_the_browser_prefers_another_language(client):
    html = html_of(client, "/", headers={"Accept-Language": "en-US,en;q=0.9,es;q=0.8"})

    assert '<html lang="pt-BR">' in html
    assert ">Experiência<" in html


def test_english_home(client):
    html = html_of(client, "/en/")
    english = load_content(settings.CONTENT_FILE, "en")

    assert '<html lang="en">' in html
    assert "Systems Analyst" in html
    assert ">Experience<" in html
    assert "May 2026 – present" in html
    assert escape(english.experiences[0].summary) in html
    assert "Send message" in html


def test_spanish_home(client):
    html = html_of(client, "/es/")
    spanish = load_content(settings.CONTENT_FILE, "es")

    assert '<html lang="es">' in html
    assert ">Experiencia<" in html
    assert "actualidad" in html
    assert escape(spanish.experiences[0].summary) in html
    assert "Enviar mensaje" in html


@pytest.mark.parametrize(
    ("url", "current"),
    [("/", "pt-BR"), ("/en/", "en"), ("/es/", "es")],
)
def test_language_switcher_links_the_three_languages_and_marks_the_current_one(
    client, url, current
):
    html = html_of(client, url)
    options = dict(
        re.findall(r'<a class="languages__option" href="([^"]+)" hreflang="([^"]+)"', html)
    )
    marked = re.findall(r'hreflang="([^"]+)"[^>]*aria-current="true"', html)

    assert options == {"/": "pt-BR", "/en/": "en", "/es/": "es"}
    assert marked == [current]


def test_each_flag_names_its_language_for_screen_readers(client):
    html = html_of(client, "/")

    for name in ("Português", "English", "Español"):
        assert f'<span class="visually-hidden">{name}</span>' in html


def test_pages_tell_search_engines_about_the_other_languages(client):
    html = html_of(client, "/en/")

    assert '<link rel="alternate" hreflang="pt-BR" href="http://testserver/">' in html
    assert '<link rel="alternate" hreflang="en" href="http://testserver/en/">' in html
    assert '<link rel="alternate" hreflang="es" href="http://testserver/es/">' in html
    assert '<link rel="alternate" hreflang="x-default" href="http://testserver/">' in html
    assert '<link rel="canonical" href="http://testserver/en/">' in html


def test_sitemap_lists_every_language(client):
    body = client.get("/sitemap.xml").content.decode()

    for url in ("http://testserver/", "http://testserver/en/", "http://testserver/es/"):
        assert f"<loc>{url}</loc>" in body


def test_health_check_has_no_language_versions(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/en/healthz").status_code == 404


# Contact form in other languages


def message(**overrides):
    data = {
        "name": "Mary Recruiter",
        "email": "mary@company.com",
        "message": "Hello Vinicius, we have an opening for a systems analyst.",
        "website": "",
        "token": new_form_token(issued_at=time.time() - 10),
    }
    data.update(overrides)
    return data


def test_english_form_confirms_in_english(client):
    response = client.post("/en/contato", message(), **JSON)

    assert response.status_code == 200
    assert response.json()["message"] == "Message sent. I will reply to the e-mail you provided."
    assert len(mail.outbox) == 1


def test_english_form_reports_errors_in_english(client):
    response = client.post("/en/contato", message(name="", email="mary"), **JSON)

    errors = response.json()["errors"]
    assert errors["name"] == ["Enter your name."]
    assert errors["email"] == ["Enter a valid e-mail."]


def test_spanish_form_reports_errors_in_spanish(client):
    response = client.post("/es/contato", message(message=""), **JSON)

    assert response.json()["errors"]["message"] == ["Escribe el mensaje."]


def test_without_javascript_english_form_returns_to_the_english_page(client):
    response = client.post("/en/contato", message())

    assert response.status_code == 302
    assert response["Location"] == "/en/?contato=enviado#contato"


def test_english_page_confirms_delivery_in_english_after_redirect(client):
    html = html_of(client, "/en/?contato=enviado")

    assert "Message sent. I will reply to the e-mail you provided." in html
