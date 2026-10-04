"""Service dispatch tests using the mock adapter."""

from __future__ import annotations

from skoiv_worker.adapters.mock import MockAdapter
from skoiv_worker.service import Service


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, message):
        self.events.append(message)


def make_service():
    rec = Recorder()
    return Service(MockAdapter(), emit=rec), rec


def test_ping():
    svc, _ = make_service()
    resp = svc.handle_request("1", "ping", {})
    assert resp["ok"] is True
    assert resp["result"]["pong"] is True
    assert resp["result"]["protocol_version"] == 1


def test_adapter_info_reports_mock():
    svc, _ = make_service()
    resp = svc.handle_request("1", "adapter.info", {})
    assert resp["result"]["name"] == "mock"
    assert resp["result"]["read_only"] is True


def test_device_detect_fixture():
    svc, _ = make_service()
    resp = svc.handle_request("1", "device.detect", {})
    devices = resp["result"]["devices"]
    assert len(devices) == 1
    assert devices[0]["chip_hint"] == "MT6768"
    assert devices[0]["vid"] == 0x0E8D


def test_gpt_read_returns_evidence():
    svc, rec = make_service()
    resp = svc.handle_request("1", "gpt.read", {})
    assert resp["ok"] is True
    result = resp["result"]
    assert result["source"] == "mock:fixture"
    assert result["header_crc32_ok"] is True
    assert result["entries_crc32_ok"] is True
    assert len(result["raw_sha256"]) == 64
    assert any(p["name"] == "preloader" and p["risk"] == "red" for p in result["partitions"])

    events = [e["event"] for e in rec.events if e["type"] == "event"]
    assert "operation-started" in events
    assert "operation-completed" in events
    assert "log" in events


def test_unknown_method_is_error_response():
    svc, _ = make_service()
    # Service-level guard (protocol also rejects unknown methods at parse time).
    resp = svc.handle_request("1", "nope", {})
    assert resp["ok"] is False
    assert resp["error"]["code"] == "unknown-method"


def test_invalid_params_produce_invalid_input():
    svc, rec = make_service()
    resp = svc.handle_request("1", "gpt.read", {"sector_size": 123})
    assert resp["ok"] is False
    assert resp["error"]["code"] == "invalid-input"
    failed = [e for e in rec.events if e.get("event") == "operation-failed"]
    assert len(failed) == 1


def test_shutdown_short_circuits():
    svc, rec = make_service()
    resp = svc.handle_request("1", "shutdown", {})
    assert resp["result"]["bye"] is True
    assert any(e.get("event") == "log" for e in rec.events)
