"""Typed adapter exceptions (docs/ARCHITECTURE.md section 6).

Messages are constants. Nothing here ever carries an upstream body, a URL, the API key or user
text, so `str(exc)` is always safe to log. `plan_trip` and `autocomplete` translate these into API
codes; this package knows nothing about HTTP responses to our own clients.
"""

from __future__ import annotations


class RoutingError(Exception):
    """Base class for every failure the ORS adapter raises."""


class LocationNotFound(RoutingError):
    """Free text geocodes to nothing in the US (LOCATION_NOT_FOUND)."""

    def __init__(self, field: str) -> None:
        super().__init__("location not found")
        self.field = field


class UnsupportedLocation(RoutingError):
    """A location resolves outside the lower 48 (UNSUPPORTED_LOCATION)."""

    def __init__(self, field: str, label: str) -> None:
        super().__init__("location outside the lower 48")
        self.field = field
        self.label = label


class RouteNotFound(RoutingError):
    """ORS 2009/2010 on the HGV request and on the one driving-car retry (ROUTE_NOT_FOUND)."""

    def __init__(self) -> None:
        super().__init__("route not found")


class TripTooLong(RoutingError):
    """ORS 2004 on a leg, or a total route over 6,000 mi (TRIP_TOO_LONG)."""

    def __init__(self) -> None:
        super().__init__("trip too long")


class UpstreamRateLimited(RoutingError):
    """ORS 429 after the one retry. `retry_after_s` is raw (header or 60); the mapper clamps it."""

    def __init__(self, retry_after_s: float = 60.0, retry_delay_s: float = 2.0) -> None:
        super().__init__("upstream rate limited")
        self.retry_after_s = retry_after_s
        self.retry_delay_s = retry_delay_s  # internal: how long the adapter itself would wait


class UpstreamQuotaExhausted(RoutingError):
    """ORS 403 (daily) or one of our own spend budgets is spent.

    `scope` is "minute" or "day"; `retry_after_s` is set only for "minute" (API_CONTRACT section 6).
    """

    def __init__(self, kind: str, scope: str = "day", retry_after_s: float | None = None) -> None:
        super().__init__("upstream quota exhausted")
        self.kind = kind
        self.scope = scope
        self.retry_after_s = retry_after_s


class UpstreamAuthError(RoutingError):
    """ORS 401, or no key configured (UPSTREAM_UNAVAILABLE, logged at CRITICAL)."""

    def __init__(self) -> None:
        super().__init__("upstream authentication failed")


class UpstreamUnavailable(RoutingError):
    """ORS 5xx, 2099, timeout or network error (UPSTREAM_UNAVAILABLE)."""

    def __init__(self, retry_delay_s: float | None = None) -> None:
        super().__init__("upstream unavailable")
        self.retry_delay_s = retry_delay_s  # internal: Retry-After hint, if any


class DeadlineExceeded(UpstreamUnavailable):
    """The request deadline passed (UPSTREAM_UNAVAILABLE)."""

    def __init__(self) -> None:
        super().__init__()
        self.args = ("deadline exceeded",)


class UpstreamBadResponse(RoutingError):
    """ORS 200 with a malformed or implausible body (UPSTREAM_UNAVAILABLE, logged at ERROR)."""

    def __init__(self) -> None:
        super().__init__("upstream returned a malformed body")


class UpstreamBadRequest(RoutingError):
    """Other ORS 4xx: our request is wrong, a bug (INTERNAL, logged at ERROR)."""

    def __init__(self) -> None:
        super().__init__("upstream rejected our request")
