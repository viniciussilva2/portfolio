"""Per-visitor rate limiting on the in-process cache.

There is no database or shared cache: counters live in the memory of each
running instance. With one or two small instances that is accurate enough to
stop a flood of contact messages.
"""

from django.core.cache import cache


def client_ip(request) -> str:
    """Address of the visitor as seen by the proxy in front of the app.

    Cloud Run appends the real client address as the last X-Forwarded-For
    entry. Anything before it was sent by the client and cannot be trusted.
    If another proxy is ever added in front (a load balancer, a CDN), the last
    entry becomes that proxy and this needs to skip it.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.rsplit(",", 1)[-1].strip() or request.META.get("REMOTE_ADDR", "")


def allow(scope: str, identity: str, *, limit: int, window: int) -> bool:
    """Count one more action for this identity; False once it passes the limit."""
    key = f"throttle:{scope}:{identity}"
    cache.add(key, 0, timeout=window)
    try:
        return cache.incr(key) <= limit
    except ValueError:  # the counter expired between add and incr
        cache.set(key, 1, timeout=window)
        return True
