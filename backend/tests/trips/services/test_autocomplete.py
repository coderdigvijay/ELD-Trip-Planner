"""autocomplete service over the real adapter with respx (docs/API_CONTRACT.md section 4)."""

from __future__ import annotations

import httpx
import pytest

from routing.errors import UpstreamQuotaExhausted, UpstreamUnavailable
from tests.trips.services.helpers import AUTOCOMPLETE_URL, feature
from trips.services.autocomplete import autocomplete


def suggestion(lng, lat, name, region="VA", **props):
    return feature(lng, lat, locality=name, region_a=region, name=name, **props)


def test_returns_labels_and_coordinates_in_relevance_order(ors):
    ors.router.get(AUTOCOMPLETE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    suggestion(-77.43605, 37.54072, "Richmond"),
                    suggestion(-84.29465, 37.74786, "Richmond", "KY"),
                ]
            },
        )
    )
    assert autocomplete("richm") == {
        "items": [
            {"label": "Richmond, VA", "lat": 37.54072, "lng": -77.43605},
            {"label": "Richmond, KY", "lat": 37.74786, "lng": -84.29465},
        ]
    }


def test_sends_the_contract_query_and_caches_the_answer(ors):
    route = ors.router.get(AUTOCOMPLETE_URL).mock(
        return_value=httpx.Response(200, json={"features": [suggestion(-77.43605, 37.54072, "Richmond")]})
    )
    first, second = autocomplete("Richm"), autocomplete("  richm ")
    assert first == second and route.call_count == 1
    params = route.calls[0].request.url.params
    assert params["boundary.country"] == "US" and params["size"] == "5"
    assert params["layers"] == "locality,address,venue,postalcode"


def test_at_most_five_items_and_non_lower_48_results_are_dropped(ors):
    features = [suggestion(-149.9, 61.2, "Anchorage", "AK")] + [
        suggestion(-77.0 - i / 10, 37.5, f"Town{i}") for i in range(8)
    ]
    ors.router.get(AUTOCOMPLETE_URL).mock(return_value=httpx.Response(200, json={"features": features}))
    items = autocomplete("town")["items"]
    assert len(items) == 5 and all("Anchorage" not in i["label"] for i in items)


def test_addresses_read_name_then_city_and_never_include_usa(ors):
    feat = feature(
        -77.43,
        37.54,
        layer="address",
        name="100 Main St",
        locality="Richmond",
        region_a="VA",
        label="100 Main St, Richmond, VA, USA",
    )
    ors.router.get(AUTOCOMPLETE_URL).mock(return_value=httpx.Response(200, json={"features": [feat]}))
    (item,) = autocomplete("100 main")["items"]
    assert item["label"] == "100 Main St, Richmond, VA" and "USA" not in item["label"]


def test_no_results_is_an_empty_list_not_an_error(ors):
    ors.router.get(AUTOCOMPLETE_URL).mock(return_value=httpx.Response(200, json={"features": []}))
    assert autocomplete("zzzzzz") == {"items": []}


def test_upstream_failure_is_typed_and_not_retried_or_cached(ors):
    route = ors.router.get(AUTOCOMPLETE_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamUnavailable):
        autocomplete("richm")
    assert route.call_count == 1
    route.mock(return_value=httpx.Response(200, json={"features": [suggestion(-77.4, 37.5, "Richmond")]}))
    assert len(autocomplete("richm")["items"]) == 1


def test_daily_quota_is_a_typed_error(ors):
    ors.router.get(AUTOCOMPLETE_URL).mock(return_value=httpx.Response(403))
    with pytest.raises(UpstreamQuotaExhausted):
        autocomplete("richm")
