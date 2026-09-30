from routing.labels import (
    KnownLabel,
    coordinate_label,
    dedupe_points,
    fallback_label,
    label_from_properties,
    reuse_known_label,
    round_point,
)

DALLAS = KnownLabel((32.7767, -96.7970), "Dallas, TX")


def test_locality_preferred():
    assert (
        label_from_properties({"locality": "Dallas", "county": "Dallas County", "region_a": "TX"})
        == "Dallas, TX"
    )


def test_localadmin_then_county_fallback():
    assert (
        label_from_properties({"localadmin": "Foo Twp", "county": "Bar", "region_a": "OH"}) == "Foo Twp, OH"
    )
    assert label_from_properties({"county": "Bar County", "region_a": "OH"}) == "Bar County, OH"


def test_missing_region_uses_label_without_usa():
    assert label_from_properties({"locality": "Dallas", "label": "Dallas, TX, USA"}) == "Dallas, TX"


def test_unusable_returns_none():
    assert label_from_properties({}) is None
    assert label_from_properties({"locality": "  ", "region_a": "TX"}) is None


def test_reuse_within_10_miles():
    assert reuse_known_label((32.85, -96.80), [DALLAS]) == "Dallas, TX"
    assert reuse_known_label((33.5, -96.8), [DALLAS]) is None
    assert reuse_known_label((32.85, -96.8), []) is None


def test_fallback_near_then_coordinates():
    assert fallback_label((33.5, -96.8), [DALLAS]) == "near Dallas, TX"
    assert fallback_label((35.004, -97.0), []) == "35.00, -97.00"
    assert coordinate_label((35.0, -97.006)) == "35.00, -97.01"


def test_round_and_dedupe():
    pts = [(35.001, -97.004), (35.004, -97.001), (36.0, -98.0), (-0.001, 1.0)]
    assert dedupe_points(pts) == [(35.0, -97.0), (36.0, -98.0), (0.0, 1.0)]
    assert str(round_point((-0.001, 1.0))[0]) == "0.0"


def test_street_label_for_addresses_and_plain_city_otherwise():
    from routing.labels import street_label_from_properties

    address = {"layer": "address", "name": "123 Main St", "locality": "Richmond", "region_a": "VA"}
    assert street_label_from_properties(address) == "123 Main St, Richmond, VA"
    assert (
        street_label_from_properties({"layer": "locality", "locality": "Richmond", "region_a": "VA"})
        == "Richmond, VA"
    )


def test_upstream_label_text_is_sanitized():
    props = {"locality": "Dal​las\x00", "region_a": "TX"}
    assert label_from_properties(props) == "Dallas, TX"


def test_fallback_far_from_every_known_label_uses_coordinates():
    assert fallback_label((37.0, -97.0), [DALLAS]) == "37.00, -97.00"  # ~330 miles
    assert fallback_label((34.5, -96.8), [DALLAS]) == "near Dallas, TX"  # ~130 miles
