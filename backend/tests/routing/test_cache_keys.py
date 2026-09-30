"""O-29 and key shape (docs/ARCHITECTURE.md section 7)."""

import math

import pytest

from routing import cache_keys as ck


def test_o29_equivalent_spellings_share_a_key():
    assert ck.geocode_key("Richmond, VA") == ck.geocode_key(" richmond,  va ")
    assert ck.autocomplete_key("Richmond, VA") == ck.autocomplete_key("\trichmond,\nva")


def test_o29_zero_width_space_is_rejected():
    with pytest.raises(ck.InvalidTextError):
        ck.geocode_key("Richmond, VA​")


@pytest.mark.parametrize("text", ["", "   ", "a\x00b", "a‮b"])
def test_rejects_empty_control_and_format_characters(text):
    with pytest.raises(ck.InvalidTextError):
        ck.normalize_text(text)


def test_nfc_composed_and_decomposed_match():
    assert ck.normalize_text("Café") == ck.normalize_text("Café")


def test_keys_are_versioned_and_kinds_do_not_collide():
    assert ck.geocode_key("x y").startswith("ors:v1:geocode:")
    assert ck.autocomplete_key("x y").startswith("ors:v1:ac:")
    assert ck.geocode_key("x y") != ck.autocomplete_key("x y")


def test_reverse_key_rounds_to_two_places_and_folds_negative_zero():
    assert ck.reverse_key(37.5449, -77.4351) == "ors:v1:rev:37.54:-77.44"
    assert ck.reverse_key(-0.001, 0.001) == ck.reverse_key(0.0, 0.0) == "ors:v1:rev:0.00:0.00"


def test_directions_key_rounds_to_five_places_and_separates_profiles():
    a = ck.directions_key("driving-hgv", (37.540721, -77.436049), (35.0, -80.0))
    b = ck.directions_key("driving-hgv", (37.540724, -77.436051), (35.0, -80.0))
    c = ck.directions_key("driving-hgv", (37.540800, -77.436049), (35.0, -80.0))
    assert a == b != c
    assert a != ck.directions_key("driving-car", (37.540721, -77.436049), (35.0, -80.0))
    assert a.startswith("ors:v1:dir:driving-hgv:")


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_non_finite_coordinates_rejected(bad):
    with pytest.raises(ValueError, match="finite"):
        ck.reverse_key(bad, 0.0)


def test_ttls_match_the_architecture_table():
    assert (ck.GEOCODE_TTL.hit_s, ck.GEOCODE_TTL.not_found_s) == (7 * 86400, 600)
    assert (ck.AUTOCOMPLETE_TTL.hit_s, ck.AUTOCOMPLETE_TTL.not_found_s) == (86400, 3600)
    assert (ck.REVERSE_TTL.hit_s, ck.REVERSE_TTL.not_found_s) == (30 * 86400, 3600)
    assert (ck.DIRECTIONS_TTL.hit_s, ck.DIRECTIONS_TTL.not_found_s) == (86400, 600)
