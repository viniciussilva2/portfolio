from django.urls import path

from . import views

# Pages that exist in every language (see config/urls.py).
urlpatterns = [
    path("", views.home, name="home"),
    path("contato", views.contact, name="contact"),
]
