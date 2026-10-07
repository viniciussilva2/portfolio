import json
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import translation
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST

from . import throttle
from .content import current_language, get_content, get_interface
from .forms import ContactForm, new_form_token

logger = logging.getLogger(__name__)

# Site language -> Django language code, value for lang/hreflang, name in that language.
SITE_LANGUAGES = (
    ("pt", "pt-br", "pt-BR", "Português"),
    ("en", "en", "en", "English"),
    ("es", "es", "es", "Español"),
)


def _language_options(request) -> list[dict]:
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
                "url": request.build_absolute_uri(path),
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


def _render_home(request, *, form=None, notice="", error="", status=200):
    content = get_content()
    ui = get_interface()
    profile = content.profile
    languages = _language_options(request)
    page_url = request.build_absolute_uri(reverse("home"))
    photo_url = request.build_absolute_uri(static(profile.photo))
    # A form that came back with a bad token must go out again with a good one.
    keep_token = form is not None and form.token_error is None
    context = {
        "content": content,
        "profile": profile,
        "ui": ui,
        "languages": languages,
        "html_lang": next(option["code"] for option in languages if option["current"]),
        "default_url": languages[0]["url"],
        "current": next((job for job in content.experiences if job.is_current), None),
        "years_unit": ui["year_one"] if profile.years_in_tech == 1 else ui["year_many"],
        "contact_form_enabled": settings.CONTACT_FORM_ENABLED,
        "form": form or ContactForm(),
        "form_token": form.data.get("token", "") if keep_token else new_form_token(),
        "contact_notice": notice,
        "contact_error": error,
        "page_url": page_url,
        "photo_url": photo_url,
        "person_json_ld": _person_json_ld(profile, page_url, photo_url),
    }
    return render(request, "portfolio/home.html", context, status=status)


@require_GET
def home(request):
    ui = get_interface()
    notice = ui["form_sent"] if request.GET.get("contato") == "enviado" else ""
    return _render_home(request, notice=notice)


@require_POST
def contact(request):
    if not settings.CONTACT_FORM_ENABLED:
        raise Http404("contact form is off: no mail server configured")
    ui = get_interface()
    wants_json = "application/json" in request.headers.get("Accept", "")
    form = ContactForm(request.POST)

    def refuse(status: int, error: str, **extra):
        if wants_json:
            return JsonResponse({"ok": False, "error": error, **extra}, status=status)
        return _render_home(request, form=form, error=error, status=status)

    def accept():
        if wants_json:
            return JsonResponse({"ok": True, "message": ui["form_sent"]})
        return redirect(f"{reverse('home')}?contato=enviado#contato")

    if not form.is_valid():
        token_error = form.token_error
        extra = {"errors": form.field_errors}
        if token_error is not None and token_error.code == "expired":
            extra["token"] = new_form_token()
        return refuse(400, token_error.message if token_error else ui["form_review"], **extra)

    visitor = throttle.client_ip(request)
    if form.cleaned_data["website"]:
        # Bots get the same answer as people, so they learn nothing.
        logger.info("contact: honeypot filled by %s, message dropped", visitor)
        return accept()

    if not throttle.allow(
        "contact",
        visitor,
        limit=settings.CONTACT_RATE_LIMIT,
        window=settings.CONTACT_RATE_WINDOW_SECONDS,
    ):
        logger.warning("contact: rate limit reached for %s", visitor)
        return refuse(429, ui["form_too_many"])

    data = form.cleaned_data
    # The owner reads Portuguese, whatever language the visitor was browsing in.
    message = EmailMessage(
        subject=f"Portfólio: mensagem de {data['name']}",
        body=(
            "Mensagem enviada pelo formulário do portfólio "
            f"(página em {current_language()}).\n\n"
            f"Nome: {data['name']}\n"
            f"E-mail: {data['email']}\n\n"
            f"{data['message']}\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.CONTACT_TO_EMAIL],
        reply_to=[data["email"]],
    )
    try:
        message.send()
    except Exception:
        # Whatever went wrong with the mail server, the visitor must be told
        # the message did not go out; the cause goes to the log.
        logger.exception("contact: could not send e-mail")
        return refuse(502, ui["form_send_failed"])
    return accept()


@require_GET
def healthz(request):
    return HttpResponse("ok", content_type="text/plain")


@require_GET
def robots(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    return HttpResponse(
        f"User-agent: *\nAllow: /\n\nSitemap: {sitemap_url}\n", content_type="text/plain"
    )


@require_GET
def sitemap(request):
    pages = "".join(
        f"  <url><loc>{option['url']}</loc></url>\n" for option in _language_options(request)
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{pages}"
        "</urlset>\n"
    )
    return HttpResponse(body, content_type="application/xml")
