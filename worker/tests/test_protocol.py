"""Protocol envelope tests (schemas/ipc/v1)."""

from __future__ import annotations

import json

import pytest

from skoiv_worker.protocol import (
    ProtocolError,
    make_error,
    make_event,
    make_log,
    make_request,
    make_response,
    parse_message,
)


def test_request_roundtrip():
    msg = make_request("device.detect", {"x": 1}, req_id="abc")
    parsed = parse_message(json.dumps(msg))
    assert parsed.kind == "request"
    assert parsed.request is not None
    assert parsed.request.id == "abc"
    assert parsed.request.method == "device.detect"
    assert parsed.request.params == {"x": 1}


def test_response_ok_and_error_shapes():
    ok = make_response("abc", {"pong": True})
    assert ok["ok"] is True and ok["result"] == {"pong": True}
    err = make_error("abc", "adapter-error", "boom", detail="stack")
    assert err["ok"] is False
    assert err["error"] == {"code": "adapter-error", "message": "boom", "detail": "stack"}


def test_event_shapes():
    ev = make_event("operation-started", {"id": "1"})
    assert ev["type"] == "event" and ev["event"] == "operation-started"
    log = make_log("info", "hello", extra_field=42)
    assert log["data"]["level"] == "info"
    assert log["data"]["extra_field"] == 42


def test_unknown_method_rejected():
    with pytest.raises(ProtocolError):
        make_request("format.disk")


def test_unknown_event_rejected():
    with pytest.raises(ProtocolError):
        make_event("device-bricked")


def test_parse_rejects_bad_json():
    with pytest.raises(ProtocolError):
        parse_message("{not json")


def test_parse_rejects_wrong_version():
    with pytest.raises(ProtocolError):
        parse_message('{"v":2,"type":"request","id":"1","method":"ping"}')


def test_parse_rejects_missing_id():
    with pytest.raises(ProtocolError):
        parse_message('{"v":1,"type":"request","method":"ping"}')


def test_parse_rejects_non_object():
    with pytest.raises(ProtocolError):
        parse_message("[1,2,3]")
