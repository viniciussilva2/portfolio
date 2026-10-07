from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path

from portfolio import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
]

# Pages exist once per language: "/" in Portuguese, "/en/" and "/es/".
urlpatterns += i18n_patterns(
    path("", include("portfolio.urls")),
    prefix_default_language=False,
)
