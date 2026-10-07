import pytest
from django.conf import settings
from django.utils import translation


@pytest.fixture(autouse=True)
def default_language():
    """A request to /en/ leaves English active on the thread; start every test in Portuguese."""
    translation.activate(settings.LANGUAGE_CODE)
    yield
    translation.activate(settings.LANGUAGE_CODE)
