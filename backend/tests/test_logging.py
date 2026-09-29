import json
import logging

from config.logging import JsonFormatter, RequestIdFilter, request_id_var


def make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord("eld.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.__dict__.update(extra)
    return record


def test_json_line_has_event_level_request_id_and_extras():
    token = request_id_var.set("abc123")
    try:
        record = make_record(status=200)
        RequestIdFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["event"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["request_id"] == "abc123"
    assert payload["status"] == 200
    assert "msg" not in payload and "args" not in payload


def test_request_line_logs_no_path_query_or_ip(client, caplog):
    with caplog.at_level(logging.INFO, logger="eld.request"):
        client.get("/api/v1/nope?q=secret-term", HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1")
    (record,) = [r for r in caplog.records if r.name == "eld.request"]
    dumped = json.dumps(record.__dict__, default=str)
    assert record.status == 404 and record.xff_hops == 2
    assert "secret-term" not in dumped and "203.0.113.9" not in dumped and "nope" not in dumped
