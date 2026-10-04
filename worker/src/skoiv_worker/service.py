"""Request dispatch: maps protocol methods onto adapter + parser operations."""

from __future__ import annotations

import platform
import sys
import time
import traceback
from typing import Any, Callable

from . import __version__
from .adapters import AdapterError, DeviceAdapter
from .gpt import GptError, parse_gpt
from .protocol import make_error, make_event, make_log, make_response

PROTOCOL_VERSION = 1


class Service:
    """Handles one worker session against a single adapter."""

    def __init__(self, adapter: DeviceAdapter, emit: Callable[[dict[str, Any]], None]) -> None:
        self.adapter = adapter
        self._emit = emit
        self._started = time.time()
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "ping": self._handle_ping,
            "adapter.info": self._handle_adapter_info,
            "device.detect": self._handle_device_detect,
            "gpt.read": self._handle_gpt_read,
        }

    # -- lifecycle ---------------------------------------------------------

    def handle_request(self, req_id: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "shutdown":
            self._emit(make_log("info", "shutdown requested by client"))
            return make_response(req_id, {"bye": True})

        handler = self._handlers.get(method)
        if handler is None:
            return make_error(req_id, "unknown-method", f"no handler for method {method!r}")

        started = time.monotonic()
        self._emit(make_event("operation-started", {"id": req_id, "method": method}))
        try:
            result = handler(params)
        except (AdapterError, GptError, ValueError) as exc:
            self._emit(
                make_event(
                    "operation-failed",
                    {"id": req_id, "method": method, "error": str(exc)},
                )
            )
            code = "adapter-error" if isinstance(exc, AdapterError) else "invalid-input"
            return make_error(req_id, code, str(exc))
        except Exception as exc:  # noqa: BLE001 - worker must survive any request
            detail = traceback.format_exc(limit=5)
            self._emit(
                make_event(
                    "operation-failed",
                    {"id": req_id, "method": method, "error": str(exc)},
                )
            )
            return make_error(req_id, "internal-error", f"{type(exc).__name__}: {exc}", detail=detail)

        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        self._emit(
            make_event(
                "operation-completed",
                {"id": req_id, "method": method, "elapsed_ms": elapsed_ms},
            )
        )
        return make_response(req_id, result)

    # -- handlers ----------------------------------------------------------

    def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "pong": True,
            "worker_version": __version__,
            "protocol_version": PROTOCOL_VERSION,
            "python": platform.python_version(),
            "uptime_s": round(time.time() - self._started, 3),
            "platform": sys.platform,
        }

    def _handle_adapter_info(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.adapter.info()

    def _handle_device_detect(self, params: dict[str, Any]) -> dict[str, Any]:
        devices = self.adapter.detect()
        return {
            "adapter": self.adapter.name,
            "devices": [d.to_dict() for d in devices],
            "hint": (
                None
                if devices
                else "No MediaTek target found. Connect the device in BROM/preloader mode "
                "(hold volume keys while plugging in USB) and ensure the WinUSB/libusb "
                "driver is bound to the port."
            ),
        }

    def _handle_gpt_read(self, params: dict[str, Any]) -> dict[str, Any]:
        if params.get("sector_size") not in (None, 512, 4096):
            raise ValueError("sector_size must be 512 or 4096")

        self._emit(make_log("info", "reading GPT (LBA 0..33)", adapter=self.adapter.name))
        image = self.adapter.read_gpt_image(sector_size=int(params.get("sector_size") or 512))
        table = parse_gpt(image.data, sector_size=image.sector_size)
        if not table.header_crc32_ok:
            self._emit(make_event("warning", {"message": "GPT header CRC mismatch", "source": image.source}))
        if not table.entries_crc32_ok:
            self._emit(make_event("warning", {"message": "GPT entries CRC mismatch", "source": image.source}))

        result = table.to_dict()
        result["source"] = image.source
        result["meta"] = image.meta
        return result
