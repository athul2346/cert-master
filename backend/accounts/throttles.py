"""Custom DRF throttles.

Render sits behind a shared proxy, so client identity via ``REMOTE_ADDR`` /
``X-Forwarded-For`` is not fully trustworthy for the auth endpoints. These
throttles key on the *targeted account* (the email in the request body), which
an attacker cannot rotate, and fall back to the client identity when no email
is supplied.
"""

from rest_framework.throttling import ScopedRateThrottle


class AccountScopedRateThrottle(ScopedRateThrottle):
    """``ScopedRateThrottle`` keyed on ``request.data["email"]`` when present."""

    def get_ident(self, request):
        try:
            data = getattr(request, "data", None)
        except Exception:  # pragma: no cover - malformed body
            data = None
        if isinstance(data, dict):
            email = str(data.get("email") or "").strip().lower()
            if email:
                return "email:" + email
        return super().get_ident(request)

    def get_cache_key(self, request, view):
        # Always use our ident (email when available), even if a session user
        # happens to be present on an anonymous auth endpoint.
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
