"""Place autocomplete (docs/API_CONTRACT.md section 4, ARCHITECTURE section 5)."""

from __future__ import annotations

from routing import ors_client
from trips.services.response import Dto, autocomplete_response


def autocomplete(q: str) -> Dto:
    """`{"items": [...]}` with at most 5 lower-48 suggestions. Upstream errors propagate typed."""
    return autocomplete_response(ors_client.autocomplete(q))
