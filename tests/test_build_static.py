"""The build that turns the site into the files GitHub Pages publishes."""

import re

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.fixture
def site(tmp_path, settings):
    """The site as "manage.py build_static" writes it, in a folder of its own."""
    settings.STATIC_BUILD = True
    settings.SITE_URL = "https://exemplo.com.br"
    settings.SITE_HOST = "exemplo.com.br"
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "exemplo.com.br"]
    output = tmp_path / "dist"
    call_command("build_static", output=str(output), verbosity=0)
    return output


def test_build_refuses_to_run_outside_a_static_build(tmp_path, settings):
    """Otherwise the pages would be written with debug on and the wrong addresses."""
    settings.STATIC_BUILD = False

    with pytest.raises(CommandError, match="DJANGO_STATIC_BUILD"):
        call_command("build_static", output=str(tmp_path / "dist"), verbosity=0)


@pytest.mark.parametrize(
    "name",
    ["index.html", "en/index.html", "es/index.html", "404.html", "robots.txt", "sitemap.xml"],
)
def test_every_page_of_the_site_is_written(site, name):
    assert (site / name).read_text(encoding="utf-8").strip()


def test_each_language_is_written_in_its_own_language(site):
    assert '<html lang="pt-BR">' in (site / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in (site / "en/index.html").read_text(encoding="utf-8")
    assert '<html lang="es">' in (site / "es/index.html").read_text(encoding="utf-8")


def test_pages_point_at_the_published_address_not_the_build_machine(site):
    html = (site / "en/index.html").read_text(encoding="utf-8")

    assert '<link rel="canonical" href="https://exemplo.com.br/en/">' in html
    assert "testserver" not in html


def test_static_files_land_next_to_the_pages(site):
    """The pages ask for /static/..., so that is where the files have to be."""
    assert (site / "static/portfolio/css/base.css").exists()
    assert (site / "static/portfolio/js/menu.js").exists()
    assert (site / "static/portfolio/fonts/michroma-latin-400-normal.woff2").exists()
    assert (site / "static/portfolio/img/vinicius.jpg").exists()


def test_every_file_the_pages_ask_for_was_written(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    asked = set(re.findall(r'(?:href|src)="/(static/[^"]+)"', html))

    assert len(asked) >= 10, "esperados CSS, JS, fontes, favicon e foto"
    assert sorted(name for name in asked if not (site / name).exists()) == []


def test_the_domain_is_kept_so_pages_does_not_drop_it(site):
    assert (site / "CNAME").read_text(encoding="utf-8").strip() == "exemplo.com.br"


def test_pages_publishes_the_files_as_they_are(site):
    """Without .nojekyll, GitHub would run the output through Jekyll first."""
    assert (site / ".nojekyll").exists()


def test_building_again_leaves_nothing_from_the_previous_build(site):
    leftover = site / "static" / "removida.css"
    leftover.write_text("/* de um build antigo */", encoding="utf-8")

    call_command("build_static", output=str(site), verbosity=0)

    assert not leftover.exists()
