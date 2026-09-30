"""DRF throttles (docs/API_CONTRACT.md section 8.1). Rates live in settings THROTTLE_RATES.

One class per (scope, window) because a DRF throttle has a single rate. Per-IP classes key on the
client address with IPv6 collapsed to its /64. Global classes share one constant key. Each class
carries the exact RATE_LIMITED message from API_CONTRACT section 6.
"""

import ipaddress
from typing import Any

from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle

from trips.errors import ApiError, ErrorCode, clamp_retry_after

IPV6_PREFIX = 64


def client_ident(request: Request) -> str:
    """Client address per NUM_PROXIES; IPv6 (and IPv4-mapped IPv6) normalized. Never raw user text."""
    raw = BaseThrottle().get_ident(request)
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        # Not an IP (cannot happen behind the verified proxy hop): fall back to the socket peer.
        return str(request.META.get("REMOTE_ADDR", "unknown"))
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/{IPV6_PREFIX}", strict=False).network_address)
    return str(address)


class _MessageMixin:
    message = "Too many requests from your network. Wait {wait} seconds, then try again."

    def failure_message(self, wait: float | None) -> tuple[str, int]:
        seconds = clamp_retry_after(wait)
        return self.message.format(wait=seconds), seconds


class PerIpThrottle(_MessageMixin, SimpleRateThrottle):
    scope = "default_ip"

    def get_cache_key(self, request: Request, view: Any) -> str:
        return self.cache_format % {"scope": self.scope, "ident": client_ident(request)}


class GlobalThrottle(_MessageMixin, SimpleRateThrottle):
    message = "The planner is at its request limit. Wait {wait} seconds, then try again."

    def get_cache_key(self, request: Request, view: Any) -> str:
        return self.cache_format % {"scope": self.scope, "ident": "global"}


class DefaultIpThrottle(PerIpThrottle):
    """Schema, docs and any view that does not choose its own throttles."""

    scope = "default_ip"


class DocsAssetsIpThrottle(PerIpThrottle):
    """Swagger UI loads about ten static files per page view, so it gets its own, wider bucket."""

    scope = "docs_assets_ip"


class PlanIpMinuteThrottle(PerIpThrottle):
    scope = "plan_ip_min"
    message = "Too many trip plans from your network. Wait {wait} seconds, then try again."


class PlanIpDayThrottle(PerIpThrottle):
    scope = "plan_ip_day"
    message = "Too many trip plans from your network. Wait {wait} seconds, then try again."


class PlanGlobalMinuteThrottle(GlobalThrottle):
    scope = "plan_global_min"


class PlanGlobalDayThrottle(GlobalThrottle):
    scope = "plan_global_day"


class PlacesIpMinuteThrottle(PerIpThrottle):
    scope = "places_ip_min"
    message = "Too many place searches from your network. Wait {wait} seconds, then try again."


class PlacesIpDayThrottle(PerIpThrottle):
    scope = "places_ip_day"
    message = "Too many place searches from your network. Wait {wait} seconds, then try again."


class PlacesGlobalMinuteThrottle(GlobalThrottle):
    scope = "places_global_min"


class PlacesGlobalDayThrottle(GlobalThrottle):
    scope = "places_global_day"


PLAN_THROTTLES = [
    PlanIpMinuteThrottle,
    PlanIpDayThrottle,
    PlanGlobalMinuteThrottle,
    PlanGlobalDayThrottle,
]
PLACES_THROTTLES = [
    PlacesIpMinuteThrottle,
    PlacesIpDayThrottle,
    PlacesGlobalMinuteThrottle,
    PlacesGlobalDayThrottle,
]


class ContractThrottleMixin:
    """Replaces DRF's generic Throttled with the contract's per-throttle RATE_LIMITED message."""

    throttled_method = "POST"  # the one method the expensive buckets apply to

    def get_throttles(self) -> list:
        """Expensive buckets for the endpoint's own method only: OPTIONS or a 405 must not drain them."""
        request = getattr(self, "request", None)
        if request is not None and request.method != self.throttled_method:
            return [DefaultIpThrottle()]
        return super().get_throttles()  # type: ignore[misc]

    def check_throttles(self, request: Request) -> None:
        for throttle in self.get_throttles():
            if not throttle.allow_request(request, self):
                message, seconds = throttle.failure_message(throttle.wait())
                raise ApiError(ErrorCode.RATE_LIMITED, message, retry_after_s=seconds)
