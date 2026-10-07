"""One public address for the site.

The same service answers on the domain, on "www." and on the address Cloud Run
gives it. Search engines would see three copies; visitors on any of the others
are sent to the main one.
"""

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonical = settings.CANONICAL_HOST
        # /healthz stays reachable everywhere: the pipeline checks each deploy
        # through the Cloud Run address.
        if canonical and request.path != "/healthz" and request.get_host() != canonical:
            return HttpResponsePermanentRedirect(
                f"{request.scheme}://{canonical}{request.get_full_path()}"
            )
        return self.get_response(request)
