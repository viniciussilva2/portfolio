"""The Content Security Policy as a <meta> tag.

GitHub Pages serves files, not headers, so the policy has to travel inside the
page itself. It is still written once, in settings.SECURE_CSP; this turns that
into the string the <meta> tag carries, minus the directives a browser ignores
there.
"""

from django.conf import settings
from django.utils.csp import build_policy

# A <meta http-equiv> policy cannot express these; browsers ignore them and log
# a warning, so they are left to the header the local server still sends.
HEADER_ONLY = frozenset({"frame-ancestors", "report-uri", "report-to", "sandbox"})


def meta_policy() -> str:
    directives = {
        name: values for name, values in settings.SECURE_CSP.items() if name not in HEADER_ONLY
    }
    return build_policy(directives)
