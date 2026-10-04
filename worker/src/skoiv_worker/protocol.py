"""IPC protocol v1: structured JSON messages over stdio (one object per line).

See schemas/ipc/v1/message-envelope.schema.json for the machine-readable
contract and docs/architecture/ipc-protocol.md for design notes.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, TextIO

PROTOCOL_VERSION = 1

KNOWN_METHODS = frozenset(
    {
        "ping",
        "adapter.info",
        "device.detect",
        "gpt.read",
        "shutdown",
    }
)

KNOWN_EVENTS = frozenset(
    {
        "worker-health",
        "log",
        "operation-started",
        "operation-progress",
        "operation-completed",
        "operation-failed",
        "warning",
    }
)


class ProtocolError(ValueError):
    """Raised when an inbound message does not satisfy the envelope contract."""


@dataclass
class Request:
    id: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedMessage:
    kind: str  # "request" | "response" | "event"
    request: Request | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def make_request(method: str, params: dict[str, Any] | None = None, req_id: str | None = None) -> dict[str, Any]:
    if method not in KNOWN_METHODS:
        raise ProtocolError(f"unknown method: {method!r}")
    return {
        "v": PROTOCOL_VERSION,
        "type": "request",
        "id": req_id or new_id(),
        "method": method,
        "params": params or {},
    }


def make_response(req_id: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "response",
        "id": req_id,
        "ok": True,
        "result": result or {},
    }


def make_error(req_id: str, code: str, message: str, detail: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if detail:
        error["detail"] = detail
    return {
        "v": PROTOCOL_VERSION,
        "type": "response",
        "id": req_id,
        "ok": False,
        "error": error,
    }


def make_event(event: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if event not in KNOWN_EVENTS:
        raise ProtocolError(f"unknown event: {event!r}")
    return {
        "v": PROTOCOL_VERSION,
        "type": "event",
        "event": event,
        "data": data or {},
    }


def make_log(level: str, message: str, **extra: Any) -> dict[str, Any]:
    data = {"level": level, "message": message, "ts": time.time()}
    data.update(extra)
    return make_event("log", data)


def parse_message(line: str) -> ParsedMessage:
    """Parse one inbound line into a validated message."""
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ProtocolError("message must be a JSON object")

    version = raw.get("v")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version: {version!r}")

    msg_type = raw.get("type")
    if msg_type == "request":
        method = raw.get("method")
        if not isinstance(method, str) or method not in KNOWN_METHODS:
            raise ProtocolError(f"unknown method: {method!r}")
        req_id = raw.get("id")
        if not isinstance(req_id, str) or not req_id:
            raise ProtocolError("request requires a non-empty string id")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            raise ProtocolError("params must be an object")
        return ParsedMessage(kind="request", request=Request(id=req_id, method=method, params=params), raw=raw)

    if msg_type in ("response", "event"):
        return ParsedMessage(kind=msg_type, raw=raw)

    raise ProtocolError(f"unknown message type: {msg_type!r}")


class MessageWriter:
    """Thread-safe line-delimited JSON writer."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdout
        self._lock = threading.Lock()

    def write(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
        with self._lock:
            self._stream.write(line + "\n")
            self._stream.flush()
