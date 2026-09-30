import polyline as pl
import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from routing.geometry import (
    METERS_PER_MILE,
    build_leg_geometry,
    build_leg_geometry_from_points,
    cumulative_haversine_m,
    decode_polyline,
    haversine_m,
    interpolate,
)

GOOGLE_EXAMPLE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


def test_decode_known_polyline_lat_lng_order():
    pts = decode_polyline(GOOGLE_EXAMPLE)
    assert pts == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_decode_empty():
    assert decode_polyline("") == []


def test_haversine_known():
    # 1 degree of latitude is about 111.2 km
    assert haversine_m((0, 0), (1, 0)) == pytest.approx(111_195, rel=1e-3)
    assert haversine_m((10, 20), (10, 20)) == 0.0


def test_rescale_matches_leg_distance_exactly():
    dist_m = 1_000_000.0
    leg = build_leg_geometry(GOOGLE_EXAMPLE, dist_m)
    assert leg.cum_miles[-1] == dist_m / METERS_PER_MILE
    assert leg.length_miles == dist_m / METERS_PER_MILE
    hav = cumulative_haversine_m(list(leg.points))[-1]
    assert leg.scale == pytest.approx(dist_m / hav)


def test_endpoints_exact_to_5dp():
    leg = build_leg_geometry(GOOGLE_EXAMPLE, 500_000.0)
    start = interpolate(leg, 0)
    end = interpolate(leg, leg.length_miles)
    assert tuple(round(x, 5) for x in start) == (38.5, -120.2)
    assert tuple(round(x, 5) for x in end) == (43.252, -126.453)


def test_clamps_out_of_range():
    leg = build_leg_geometry(GOOGLE_EXAMPLE, 500_000.0)
    assert interpolate(leg, -5) == leg.points[0]
    assert interpolate(leg, 1e9) == leg.points[-1]


def test_midpoint_of_straight_segment():
    leg = build_leg_geometry_from_points([(0.0, 0.0), (0.0, 2.0)], 200 * METERS_PER_MILE)
    lat, lng = interpolate(leg, 100)
    assert (lat, lng) == pytest.approx((0.0, 1.0))


def test_zero_length_leg_returns_point():
    leg = build_leg_geometry_from_points([(41.0, -87.0), (41.0, -87.0)], 0.0)
    assert interpolate(leg, 0) == (41.0, -87.0)
    assert interpolate(leg, 12) == (41.0, -87.0)


def test_single_vertex_and_empty_polyline_string():
    leg = build_leg_geometry(pl.encode([(41.0, -87.0)]), 0.0)
    assert interpolate(leg, 3.0) == pytest.approx((41.0, -87.0))
    empty = build_leg_geometry("", 0.0)
    with pytest.raises(ValueError, match="empty"):
        interpolate(empty, 0)


def test_duplicate_vertices_do_not_divide_by_zero():
    leg = build_leg_geometry_from_points([(0.0, 0.0), (0.0, 0.0), (0.0, 1.0)], 100 * METERS_PER_MILE)
    assert interpolate(leg, 50) == pytest.approx((0.0, 0.5))


lat = st.floats(25, 49, allow_nan=False)
lng = st.floats(-124, -67, allow_nan=False)


@example(points=[(25.0, -124.0), (25.0, -124.0), (25.00001, -124.0), (25.00001, -124.0)], miles=1.0)
@example(points=[(30.0, -100.0), (30.0, -100.00001), (30.0, -100.00001)], miles=2999.9999999)
@given(st.lists(st.tuples(lat, lng), min_size=2, max_size=30), st.floats(1, 3000))
def test_interpolation_properties(points, miles):
    pts = [(round(a, 5), round(b, 5)) for a, b in points]
    leg = build_leg_geometry_from_points(pts, miles * METERS_PER_MILE)
    assert interpolate(leg, 0) == pts[0]
    if len(set(pts)) > 1:
        assert interpolate(leg, leg.length_miles) == pts[-1]
    cum = list(leg.cum_miles)
    assert cum == sorted(cum)
    if len(set(pts)) > 1:
        assert cum[-1] == leg.length_miles
    for i in range(21):
        lat_, lng_ = interpolate(leg, leg.length_miles * i / 20)
        assert min(a for a, _ in pts) - 1e-9 <= lat_ <= max(a for a, _ in pts) + 1e-9
        assert min(b for _, b in pts) - 1e-9 <= lng_ <= max(b for _, b in pts) + 1e-9


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_interpolate_rejects_non_finite_miles(bad):
    leg = build_leg_geometry(GOOGLE_EXAMPLE, 500_000.0)
    with pytest.raises(ValueError, match="finite"):
        interpolate(leg, bad)
