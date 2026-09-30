"""In-flight plan guards (docs/API_CONTRACT.md 8.2): 1 per client, 3 global.

Each slot is an atomic `cache.add` (30 s timeout, longer than the 25 s request deadline) and is
released in `__exit__`, so a crash, an exception or a client disconnect frees it. Slots are
distinct keys, so no read-modify-write race exists.
"""

from types import TracebackType

from django.core.cache import caches
from rest_framework.request import Request

from trips.errors import ApiError, ErrorCode
from trips.throttles import client_ident

GLOBAL_SLOTS = 3
SLOT_TIMEOUT_S = 30
RETRY_AFTER_S = 5
CACHE_ALIAS = "default"
PER_IP_MESSAGE = "Your previous trip is still being planned. Wait for it to finish, then try again."
GLOBAL_MESSAGE = "The planner is busy with other trips. Wait 5 seconds, then try again."


class PlanInflightGuard:
    def __init__(self, request: Request) -> None:
        self._ip_key = f"inflight:plan:ip:{client_ident(request)}"
        self._held: list[str] = []

    def __enter__(self) -> "PlanInflightGuard":
        cache = caches[CACHE_ALIAS]
        if not cache.add(self._ip_key, 1, timeout=SLOT_TIMEOUT_S):
            raise ApiError(ErrorCode.RATE_LIMITED, PER_IP_MESSAGE, retry_after_s=RETRY_AFTER_S)
        self._held.append(self._ip_key)
        for slot in range(GLOBAL_SLOTS):
            key = f"inflight:plan:global:{slot}"
            if cache.add(key, 1, timeout=SLOT_TIMEOUT_S):
                self._held.append(key)
                return self
        self._release()
        raise ApiError(ErrorCode.RATE_LIMITED, GLOBAL_MESSAGE, retry_after_s=RETRY_AFTER_S)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._release()

    def _release(self) -> None:
        cache = caches[CACHE_ALIAS]
        for key in self._held:
            cache.delete(key)
        self._held.clear()
