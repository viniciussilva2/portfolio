import dataclasses
import json
import re
from urllib.parse import urljoin

import pytest
from django.utils.html import escape

from portfolio import views
from portfolio.content import get_content


@pytest.fixture
def home_html(client):
    response = client.get("/")
    assert response.status_code == 200
    return response.content.decode()


def test_healthz_answers_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.content == b"ok"


def test_home_shows_name_role_and_tagline(home_html):
    profile = get_content().profile

    assert profile.name in home_html
    assert profile.role in home_html
    assert escape(profile.tagline) in home_html


def test_home_lists_every_experience_with_period(home_html):
    for experience in get_content().experiences:
        assert escape(experience.company) in home_html
        assert escape(experience.role) in home_html
        assert experience.period in home_html


def test_home_lists_every_skill(home_html):
    for group in get_content().skill_groups:
        assert escape(group.name) in home_html
        for skill in group.skills:
            assert escape(skill) in home_html


def test_home_lists_every_project(home_html):
    for project in get_content().projects:
        assert escape(project.title) in home_html


def test_home_links_each_github_project_to_its_repository(home_html):
    for project in get_content().github_projects:
        assert f'href="{project.url}"' in home_html


def test_home_shows_how_ai_is_used_and_with_which_tools(home_html):
    ai = get_content().ai

    assert 'id="ia"' in home_html
    assert escape(ai.summary) in home_html
    for tool in ai.tools:
        assert escape(tool.name) in home_html
        assert escape(tool.use) in home_html


def test_home_has_no_ai_section_or_menu_link_when_content_has_none(client, monkeypatch):
    without_ai = dataclasses.replace(get_content(), ai=None)
    monkeypatch.setattr(views, "get_content", lambda: without_ai)

    html = client.get("/").content.decode()

    assert 'id="ia"' not in html
    assert 'href="#ia"' not in html


def test_home_shows_the_logo_of_every_company_and_ai_tool(home_html):
    content = get_content()
    with_logo = [*content.experiences, *content.ai.tools]

    assert all(item.logo for item in with_logo), "toda empresa e ferramenta de IA tem logo"
    for item in with_logo:
        assert f'src="/static/{item.logo}"' in home_html


def test_logo_drawn_in_white_gets_a_dark_ground(home_html):
    dark = [job for job in get_content().experiences if job.logo_ground == "dark"]

    assert dark, "ao menos uma logo do conteúdo publicado é branca"
    assert home_html.count('class="logo logo--dark"') == len(dark)


def test_home_shows_education(home_html):
    for education in get_content().education:
        assert escape(education.institution) in home_html
        assert escape(education.course) in home_html


def test_home_links_linkedin_and_github_profiles(home_html):
    links = get_content().profile.links

    assert f'href="{links.linkedin}"' in home_html
    assert f'href="{links.github}"' in home_html


def test_home_has_contact_form_posting_to_contact_endpoint(home_html):
    assert 'action="/contato"' in home_html
    assert 'name="csrfmiddlewaretoken"' in home_html


def _content_with_links(**changes):
    content = get_content()
    links = dataclasses.replace(content.profile.links, **changes)
    return dataclasses.replace(content, profile=dataclasses.replace(content.profile, links=links))


def test_home_hides_whatsapp_link_when_number_is_not_set(client, monkeypatch):
    monkeypatch.setattr(views, "get_content", lambda: _content_with_links(whatsapp=""))

    assert "wa.me" not in client.get("/").content.decode()


def test_home_links_whatsapp_when_number_is_set(client, monkeypatch):
    monkeypatch.setattr(views, "get_content", lambda: _content_with_links(whatsapp="5571900000000"))

    assert 'href="https://wa.me/5571900000000"' in client.get("/").content.decode()


def test_home_hides_email_link_when_email_is_not_set(client, monkeypatch):
    monkeypatch.setattr(views, "get_content", lambda: _content_with_links(email=""))

    assert "mailto:" not in client.get("/").content.decode()


def _json_ld(html):
    block = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    assert block, "página sem bloco JSON-LD"
    return json.loads(block[1])


def test_home_describes_the_person_for_search_engines(home_html):
    profile = get_content().profile
    person = _json_ld(home_html)

    assert person["@type"] == "Person"
    assert person["name"] == profile.name
    assert person["jobTitle"] == profile.role
    assert person["url"] == "http://testserver/"
    assert set(person["sameAs"]) == {profile.links.linkedin, profile.links.github}


def test_json_ld_cannot_be_broken_out_of_by_content_text(client, monkeypatch):
    content = get_content()
    hostile = dataclasses.replace(content.profile, tagline="</script><script>alert(1)</script>")
    monkeypatch.setattr(views, "get_content", lambda: dataclasses.replace(content, profile=hostile))

    html = client.get("/").content.decode()

    assert "<script>alert(1)" not in html
    assert _json_ld(html)["description"] == "</script><script>alert(1)</script>"


def test_robots_allows_crawling_and_points_to_sitemap(client):
    response = client.get("/robots.txt")
    body = response.content.decode()

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert "Allow: /" in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


def test_sitemap_lists_home_page(client):
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")
    assert "<loc>http://testserver/</loc>" in response.content.decode()


def test_every_asset_the_page_loads_exists(client, home_html):
    assets = set(re.findall(r'(?:href|src)="(/static/[^"]+)"', home_html))

    assert len(assets) >= 10, "esperados CSS, JS, fontes, favicon e foto"
    missing = sorted(url for url in assets if client.get(url).status_code != 200)
    assert missing == []


def test_stylesheets_only_reference_files_that_exist(client, home_html):
    stylesheets = re.findall(r'href="(/static/[^"]+\.css)"', home_html)
    missing = []
    for stylesheet in stylesheets:
        css = b"".join(client.get(stylesheet).streaming_content).decode()
        for reference in re.findall(r'url\("?([^")]+)"?\)', css):
            url = urljoin(stylesheet, reference)
            if client.get(url).status_code != 200:
                missing.append(url)

    assert stylesheets
    assert missing == []


def test_unknown_page_returns_404(client):
    assert client.get("/nao-existe").status_code == 404
