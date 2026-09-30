"""Request validation matrix (docs/TEST_PLAN.md 5.3). The service is patched: this is the trust boundary."""

import datetime as dt
import json

import pytest

from tests.trips.conftest import PLAN_URL, TODAY, post_plan, valid_payload


def _assert_400(response, field=None):
    assert response.status_code == 400, response.content
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]
    if field is not None:
        assert error["field"] == field
    return error


@pytest.mark.parametrize(
    "value",
    [-0.25, 70.25, 12.3, "12", True, False, None, 71, [], {}, 10**400],
)
def test_bad_cycle_hours(client, plan_service, value):
    response = post_plan(client, valid_payload(current_cycle_used_hours=value))
    error = _assert_400(response, "current_cycle_used_hours")
    assert error["message"] == "Cycle hours must be between 0 and 70, in steps of 0.25."
    plan_service.assert_not_called()


def test_exponent_overflow_literal_is_rejected_as_non_finite(client, plan_service):
    raw = json.dumps(valid_payload()).replace(
        '"current_cycle_used_hours": 10', '"current_cycle_used_hours": 1e309'
    )
    response = client.post(PLAN_URL, raw, content_type="application/json")
    _assert_400(response, "current_cycle_used_hours")


def test_missing_cycle_hours(client, plan_service):
    body = valid_payload()
    del body["current_cycle_used_hours"]
    _assert_400(post_plan(client, body), "current_cycle_used_hours")


def test_nan_literal_is_invalid_json(client, plan_service):
    raw = '{"current_cycle_used_hours": NaN}'
    response = client.post(PLAN_URL, raw, content_type="application/json")
    assert _assert_400_message(response) == "The request body is not valid JSON."


def _assert_400_message(response):
    assert response.status_code == 400
    return response.json()["error"]["message"]


@pytest.mark.parametrize("value", [0, 0.25, 34.75, 69.5, 70, 70.0])
def test_good_cycle_hours(client, plan_service, value):
    assert post_plan(client, valid_payload(current_cycle_used_hours=value)).status_code == 200
    assert plan_service.call_args.args[0]["current_cycle_used_hours"] == float(value)


@pytest.mark.parametrize("value", ["8:00", "08:10", "24:00", "23:46", "", 800, None, "08:00:00", "8am"])
def test_bad_start_time(client, plan_service, value):
    _assert_400(post_plan(client, valid_payload(start_time=value)), "start_time")


@pytest.mark.parametrize("value", ["00:00", "23:45", "08:15"])
def test_good_start_time(client, plan_service, value):
    assert post_plan(client, valid_payload(start_time=value)).status_code == 200
    assert plan_service.call_args.args[0]["start_time"].strftime("%H:%M") == value


def test_start_time_default_and_date_default(client, plan_service):
    body = valid_payload()
    del body["start_time"], body["start_date"]
    assert post_plan(client, body).status_code == 200
    validated = plan_service.call_args.args[0]
    assert validated["start_time"] == dt.time(8, 0)
    assert validated["start_date"] is None


@pytest.mark.parametrize(
    "value",
    [
        "2026-13-01",
        (TODAY - dt.timedelta(days=31)).isoformat(),
        (TODAY + dt.timedelta(days=366)).isoformat(),
        "05/10/2026",
        "20261005",
        "2026-10-05T00:00:00",
        20261005,
        "",
    ],
)
def test_bad_start_date(client, plan_service, value):
    _assert_400(post_plan(client, valid_payload(start_date=value)), "start_date")


@pytest.mark.parametrize(
    "value", [(TODAY - dt.timedelta(days=30)).isoformat(), (TODAY + dt.timedelta(days=365)).isoformat()]
)
def test_start_date_boundaries_accepted(client, plan_service, value):
    assert post_plan(client, valid_payload(start_date=value)).status_code == 200


@pytest.mark.parametrize(
    "value",
    ["", "ab", "a" * 201, "Rich\nmond", "Rich​mond", "‮evil", "Rich\tmond", "   ", 5, True, [], None],
)
def test_bad_free_text_location(client, plan_service, value):
    _assert_400(post_plan(client, valid_payload(pickup_location=value)), "pickup_location")


def test_free_text_is_trimmed_nfc_and_collapsed(client, plan_service):
    decomposed = "  Española,   NM "
    assert post_plan(client, valid_payload(pickup_location=decomposed)).status_code == 200
    assert plan_service.call_args.args[0]["pickup_location"] == "Española, NM"


def test_unicode_label_round_trips(client, plan_service):
    place = {"label": "Española, NM", "lat": 35.99, "lng": -106.08}
    assert post_plan(client, valid_payload(pickup_location=place)).status_code == 200
    assert plan_service.call_args.args[0]["pickup_location"] == place


@pytest.mark.parametrize(
    ("place", "field"),
    [
        ({"label": "X", "lat": 91, "lng": -77}, "current_location.lat"),
        ({"label": "X", "lat": 37, "lng": -181}, "current_location.lng"),
        ({"label": "", "lat": 37, "lng": -77}, "current_location.label"),
        ({"label": "a" * 201, "lat": 37, "lng": -77}, "current_location.label"),
        ({"label": "X", "lng": -77}, "current_location.lat"),
        ({"label": "X", "lat": "37", "lng": -77}, "current_location.lat"),
        ({"label": "X", "lat": True, "lng": -77}, "current_location.lat"),
        ({"label": "X", "lat": 37, "lng": None}, "current_location.lng"),
        ({"label": "X\nY", "lat": 37, "lng": -77}, "current_location.label"),
        ({"label": "X", "lat": 10**400, "lng": -77}, "current_location.lat"),
    ],
)
def test_bad_place_input(client, plan_service, place, field):
    _assert_400(post_plan(client, valid_payload(current_location=place)), field)


@pytest.mark.parametrize(
    "place",
    [
        {"label": "Anchorage, AK", "lat": 61.2, "lng": -149.9},
        {"label": "Honolulu, HI", "lat": 21.3, "lng": -157.8},
        {"label": "Edge", "lat": 23.99, "lng": -100},
        {"label": "Edge", "lat": 50, "lng": -100},
        {"label": "Edge", "lat": 40, "lng": -66.4},
        {"label": "Edge", "lat": 40, "lng": -125.1},
    ],
)
def test_place_outside_lower_48_is_unsupported_location(client, plan_service, place):
    response = post_plan(client, valid_payload(current_location=place))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "UNSUPPORTED_LOCATION"
    assert error["field"] == "current_location"
    assert place["label"] in error["message"]
    plan_service.assert_not_called()


@pytest.mark.parametrize(
    "place", [{"label": "SW", "lat": 24.0, "lng": -125.0}, {"label": "NE", "lat": 49.5, "lng": -66.5}]
)
def test_lower_48_box_edges_are_inside(client, plan_service, place):
    assert post_plan(client, valid_payload(current_location=place)).status_code == 200


def test_unsupported_location_names_the_field(client, plan_service):
    place = {"label": "Honolulu, HI", "lat": 21.3, "lng": -157.8}
    error = post_plan(client, valid_payload(dropoff_location=place)).json()["error"]
    assert error["field"] == "dropoff_location"


@pytest.mark.parametrize(
    ("driver", "ok"),
    [("x" * 80, True), ("x" * 81, False), (None, True), ("", True), ("  ", True), ("a\nb", False)],
)
def test_log_header_driver_name(client, plan_service, driver, ok):
    response = post_plan(client, valid_payload(log_header={"driver_name": driver}))
    assert (response.status_code == 200) is ok
    if not ok:
        _assert_400(response, "log_header.driver_name")


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("driver_name", 80),
        ("carrier_name", 100),
        ("main_office_address", 150),
        ("home_terminal_address", 150),
        ("truck_number", 40),
        ("trailer_number", 40),
        ("shipping_doc", 60),
        ("shipper_commodity", 100),
    ],
)
def test_log_header_limits(client, plan_service, field, limit):
    assert post_plan(client, valid_payload(log_header={field: "y" * limit})).status_code == 200
    error = _assert_400(post_plan(client, valid_payload(log_header={field: "y" * (limit + 1)})))
    assert error["field"] == f"log_header.{field}"
    control = post_plan(client, valid_payload(log_header={field: "a​b"}))
    _assert_400(control, f"log_header.{field}")


def test_log_header_defaults_are_blank_strings(client, plan_service):
    body = valid_payload()
    del body["log_header"]
    assert post_plan(client, body).status_code == 200
    header = plan_service.call_args.args[0]["log_header"]
    assert set(header) == {
        "driver_name",
        "carrier_name",
        "main_office_address",
        "home_terminal_address",
        "truck_number",
        "trailer_number",
        "shipping_doc",
        "shipper_commodity",
    }
    assert set(header.values()) == {""}


def test_log_header_null_is_accepted(client, plan_service):
    assert post_plan(client, valid_payload(log_header=None)).status_code == 200


def test_log_header_must_be_object(client, plan_service):
    _assert_400(post_plan(client, valid_payload(log_header="John")), "log_header")


def test_multiple_errors_are_all_listed(client, plan_service):
    error = _assert_400(
        post_plan(client, valid_payload(current_cycle_used_hours=71, start_time="8:00", pickup_location="ab"))
    )
    assert {d["field"] for d in error["details"]} == {
        "current_cycle_used_hours",
        "start_time",
        "pickup_location",
    }
    assert error["field"] == error["details"][0]["field"]


def test_pickup_equals_dropoff_free_text_ignores_case_and_spacing(client, plan_service):
    body = valid_payload(pickup_location="Newark,  NJ", dropoff_location="newark, nj")
    error = _assert_400(post_plan(client, body), "dropoff_location")
    assert error["message"] == "Pickup and dropoff are the same place. Choose a different dropoff."


def test_pickup_equals_dropoff_places_compare_at_five_decimals(client, plan_service):
    a = {"label": "A", "lat": 40.735661, "lng": -74.172371}
    b = {"label": "Different label", "lat": 40.735664, "lng": -74.172374}
    _assert_400(post_plan(client, valid_payload(pickup_location=a, dropoff_location=b)), "dropoff_location")
    c = {"label": "A", "lat": 40.73567, "lng": -74.17237}
    assert post_plan(client, valid_payload(pickup_location=a, dropoff_location=c)).status_code == 200


def test_current_may_equal_pickup_or_dropoff(client, plan_service):
    place = {"label": "Richmond, VA", "lat": 37.54072, "lng": -77.43605}
    body = valid_payload(current_location=place, pickup_location=place)
    assert post_plan(client, body).status_code == 200
    body = valid_payload(current_location=place, dropoff_location=place)
    assert post_plan(client, body).status_code == 200


def test_unknown_fields_are_ignored_and_dropped(client, plan_service):
    body = valid_payload(surprise="x")
    body["current_location"] = {**body["current_location"], "extra": 1}
    assert post_plan(client, body).status_code == 200
    validated = plan_service.call_args.args[0]
    assert "surprise" not in validated
    assert set(validated["current_location"]) == {"label", "lat", "lng"}


def test_validated_dict_shape_matches_plan_request(client, plan_service):
    assert post_plan(client, valid_payload()).status_code == 200
    validated = plan_service.call_args.args[0]
    assert set(validated) == {
        "current_location",
        "pickup_location",
        "dropoff_location",
        "current_cycle_used_hours",
        "start_date",
        "start_time",
        "log_header",
    }
    assert validated["start_date"] == dt.date(2026, 10, 5)
    assert isinstance(validated["current_cycle_used_hours"], float)


def test_integer_and_float_coordinates_both_accepted(client, plan_service):
    place = {"label": "X", "lat": 40, "lng": -100}
    assert post_plan(client, valid_payload(current_location=place)).status_code == 200
    assert isinstance(plan_service.call_args.args[0]["current_location"]["lat"], float)


# --- body limits, in the contract's order ---------------------------------------------------------


def test_body_over_8kb_rejected_from_content_length(client, plan_service):
    body = b'{"x": "' + b"a" * 8200 + b'"}'
    response = client.post(PLAN_URL, body, content_type="application/json")
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "The request body is larger than 8 KB."


def test_body_of_exactly_8192_bytes_is_read_then_validated(client, plan_service):
    pad = 8192 - len(b'{"x": ""}')
    response = client.post(PLAN_URL, b'{"x": "' + b"a" * pad + b'"}', content_type="application/json")
    assert response.status_code == 400
    assert response.json()["error"]["details"]  # got past the size gate and failed field validation


@pytest.mark.parametrize("length", ["", "abc", "-1"])
def test_missing_or_bad_content_length_rejected(client, plan_service, length):
    response = client.generic("POST", PLAN_URL, b"{}", "application/json", CONTENT_LENGTH=length)
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "The request body is larger than 8 KB."


def test_lying_content_length_cannot_exceed_parser_cap(client, plan_service):
    from trips.parsers import BoundedJSONParser

    class Stream:
        def read(self, n):
            return b"a" * n

    from trips.errors import ApiError

    with pytest.raises(ApiError):
        BoundedJSONParser().parse(Stream())


def test_wrong_content_type(client, plan_service):
    response = client.post(PLAN_URL, "{}", content_type="text/plain")
    assert response.status_code == 400
    assert response.json()["error"]["message"] == (
        "Send the request body as JSON (Content-Type: application/json)."
    )


def test_content_type_with_charset_is_accepted(client, plan_service):
    response = client.post(PLAN_URL, "{}", content_type="application/json; charset=utf-8")
    assert response.status_code == 400  # empty object: fields missing, not a content-type error
    assert response.json()["error"]["details"]


@pytest.mark.parametrize(
    "raw", ["{bad", "[]", '"text"', "null", "5", "", '{"a": Infinity}', '{"a": -Infinity}']
)
def test_invalid_json_or_non_object(client, plan_service, raw):
    response = client.post(PLAN_URL, raw, content_type="application/json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert "Traceback" not in error["message"]


def test_deeply_nested_json_is_400_not_500(client, plan_service):
    raw = "[" * 4000 + "]" * 4000
    response = client.post(PLAN_URL, raw, content_type="application/json")
    assert response.status_code == 400


def test_invalid_utf8_is_400(client, plan_service):
    response = client.post(PLAN_URL, b'{"a": "\xff\xfe"}', content_type="application/json")
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "The request body is not valid JSON."


def test_size_check_runs_before_throttling(client, plan_service):
    for _ in range(12):
        client.post(PLAN_URL, b"x" * 9000, content_type="application/json")
    assert post_plan(client, valid_payload()).status_code == 200  # oversized bodies never spent the bucket
