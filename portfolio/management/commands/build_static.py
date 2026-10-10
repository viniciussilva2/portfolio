"""Renders the whole site to files, for publishing on GitHub Pages.

    DJANGO_STATIC_BUILD=1 python manage.py build_static

Every address the site has is requested once, in process, and the answer is
written where GitHub Pages expects to find it:

    dist/index.html      the home page, in Portuguese
    dist/en/index.html   the same page in English
    dist/es/index.html   and in Spanish
    dist/404.html        the page Pages answers with for unknown addresses
    dist/robots.txt      dist/sitemap.xml
    dist/static/...      CSS, JavaScript, fonts and images
    dist/CNAME           the domain, so Pages keeps serving it after a deploy
    dist/.nojekyll       Pages publishes the files as they are, no Jekyll

The addresses inside the pages (canonical, hreflang, sitemap, JSON-LD) come
from settings.SITE_URL, not from the machine running the build.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings

# Address to request -> file to write, relative to the output folder.
PAGES = {
    "/": "index.html",
    "/en/": "en/index.html",
    "/es/": "es/index.html",
    "/404.html": "404.html",
    "/robots.txt": "robots.txt",
    "/sitemap.xml": "sitemap.xml",
}


class Command(BaseCommand):
    help = "Renders the site to a folder of files ready for GitHub Pages."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="dist",
            help="Folder to write the site into; emptied first. Default: dist",
        )

    def handle(self, *args, **options):
        if not settings.STATIC_BUILD:
            raise CommandError(
                "run with DJANGO_STATIC_BUILD=1, so the site is rendered with "
                "debug off and the published addresses in place"
            )
        if not settings.SITE_HOST:
            raise CommandError(f"SITE_URL has no host: {settings.SITE_URL!r}")

        output = Path(options["output"]).resolve()
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)

        self._collect_static(output / "static")
        self._render_pages(output)
        self._write_pages_files(output)

        self.stdout.write(self.style.SUCCESS(f"Site rendered in {output}"))

    def _collect_static(self, destination: Path) -> None:
        # collectstatic only ever writes to STATIC_ROOT, so point it at the
        # output folder for as long as it runs.
        with override_settings(STATIC_ROOT=str(destination)):
            call_command("collectstatic", interactive=False, verbosity=0)

    def _render_pages(self, output: Path) -> None:
        secure = settings.SITE_URL.startswith("https://")
        client = Client()
        for url, name in PAGES.items():
            response = client.get(url, secure=secure, SERVER_NAME=settings.SITE_HOST)
            if response.status_code != 200:
                raise CommandError(f"{url} answered {response.status_code}, expected 200")
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
            self.stdout.write(f"  {url} -> {name}")

    def _write_pages_files(self, output: Path) -> None:
        # Without CNAME the custom domain is dropped on the next deploy.
        (output / "CNAME").write_text(f"{settings.SITE_HOST}\n", encoding="utf-8")
        (output / ".nojekyll").write_text("", encoding="utf-8")
