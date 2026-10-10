import json

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import translation
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET

from .content import current_language, get_content, get_interface
from .csp import meta_policy

# Site language -> Django language code, value for lang/hreflang, name in that language.
SITE_LANGUAGES = (
    ("pt", "pt-br", "pt-BR", "Português"),
    ("en", "en", "en", "English"),
    ("es", "es", "es", "Español"),
)


def _site_url(path: str) -> str:
    """Address a page has on the published site.

    The build renders pages with no visitor and no real request, so addresses
    come from settings.SITE_URL rather than from the host that served them.
    """
    return f"{settings.SITE_URL}{path}"


def _language_options() -> list[dict]:
    """The home page in each language, for the flag switcher and for search engines."""
    active = current_language()
    options = []
    for key, django_code, html_code, name in SITE_LANGUAGES:
        with translation.override(django_code):
            path = reverse("home")
        options.append(
            {
                "key": key,
                "code": html_code,
                "name": name,
                "path": path,
                "url": _site_url(path),
                "current": key == active,
            }
        )
    return options


def _person_json_ld(profile, page_url: str, photo_url: str):
    """schema.org description of the person, safe to place inside a <script> block."""
    data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": profile.name,
        "jobTitle": profile.role,
        "description": profile.tagline,
        "url": page_url,
        "image": photo_url,
        "sameAs": [profile.links.linkedin, profile.links.github],
    }
    escaped = (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003C")
        .replace(">", "\\u003E")
        .replace("&", "\\u0026")
    )
    return mark_safe(escaped)


def _page_context(path: str) -> dict:
    """What every page needs: the content, the texts and the page's own address."""
    content = get_content()
    languages = _language_options()
    return {
        "content": content,
        "profile": content.profile,
        "ui": get_interface(),
        "languages": languages,
        "html_lang": next(option["code"] for option in languages if option["current"]),
        "default_url": languages[0]["url"],
        "page_url": _site_url(path),
        "csp": meta_policy(),
    }


@require_GET
def home(request):
    content = get_content()
    profile = content.profile
    ui = get_interface()
    context = _page_context(reverse("home"))
    photo_url = _site_url(static(profile.photo))
    context.update(
        {
            "current": next((job for job in content.experiences if job.is_current), None),
            "years_unit": ui["year_one"] if profile.years_in_tech == 1 else ui["year_many"],
            "photo_url": photo_url,
            "person_json_ld": _person_json_ld(profile, context["page_url"], photo_url),
        }
    )
    return render(request, "portfolio/home.html", context)


@require_GET
def not_found(request):
    """The page GitHub Pages serves for an address that does not exist.

    Pages looks for /404.html and answers with it, so the file is rendered like
    any other page. It is in Portuguese: there is no request to pick a language
    from when a visitor lands on an address that was never ours.
    """
    return render(request, "portfolio/404.html", _page_context("/404.html"))


@require_GET
def robots(request):
    return HttpResponse(
        f"User-agent: *\nAllow: /\n\nSitemap: {_site_url(reverse('sitemap'))}\n",
        content_type="text/plain",
    )


@require_GET
def sitemap(request):
    pages = "".join(f"  <url><loc>{option['url']}</loc></url>\n" for option in _language_options())
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{pages}"
        "</urlset>\n"
    )
    return HttpResponse(body, content_type="application/xml")
