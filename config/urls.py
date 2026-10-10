from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path

from portfolio import views

# Files the published site keeps at its root, in one language.
# "404.html" is an address so the build can render it like any other page;
# GitHub Pages then answers with that file for any address that does not exist.
urlpatterns = [
    path("404.html", views.not_found, name="not_found"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
]

# Pages exist once per language: "/" in Portuguese, "/en/" and "/es/".
urlpatterns += i18n_patterns(
    path("", include("portfolio.urls")),
    prefix_default_language=False,
)
