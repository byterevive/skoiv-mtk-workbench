"""Real-device adapter implemented on top of mtkclient (optional dependency).

mtkclient is GPLv3 upstream software (https://github.com/bkerler/mtkclient),
accessed only through this Workbench-owned adapter (ADR-0006). The dependency
is an optional extra (``skoiv-worker[device]``) so the worker remains runnable
and testable without it.

The interaction pattern follows upstream's own ``mtk_api.py`` example:
MtkConfig -> Mtk -> DaHandler.connect -> configure_da -> da_rs (raw reads).
Version 0.1 issues reads only (ADR-0007).
"""

from __future__ import annotations

import logging
import sys
import types
from typing import Any

from .base import AdapterError, DetectedDevice, DeviceAdapter, RawDiskImage

# Subset of mtkclient.config.usb_ids.default_ids used when that module cannot
# be imported. VID -> {PID: note}.
_FALLBACK_USB_IDS: dict[int, dict[int, str]] = {
    0x0E8D: {
        0x0003: "MediaTek BROM",
        0x2000: "MediaTek Preloader",
        0x2001: "MediaTek Preloader",
        0x20FF: "MediaTek Preloader",
        0x3000: "MediaTek Preloader",
        0x6000: "MediaTek Preloader",
    },
    0x22D9: {0x0006: "OPPO Preloader"},
    0x1004: {0x6000: "LG Preloader"},
}


def _ensure_fuse_importable() -> bool:
    """Make ``import fuse`` succeed without a system libfuse.

    mtkclient's DA filesystem helper imports fusepy at module import time, but
    the Workbench never mounts DA partitions via FUSE. When fusepy cannot find
    libfuse/WinFsp it raises OSError at import; stub the module so the rest of
    mtkclient stays importable. Returns True when a stub was installed.
    """
    try:
        import fuse  # noqa: F401,PLC0415
        return False
    except Exception:  # noqa: BLE001 - fusepy raises OSError, ImportError...
        pass

    stub = types.ModuleType("fuse")

    class Operations:  # minimal stand-ins for the classes mtkclient subclasses
        pass

    class LoggingMixIn:
        pass

    class FUSE:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("FUSE mounting is not available in this environment")

    stub.Operations = Operations
    stub.LoggingMixIn = LoggingMixIn
    stub.FUSE = FUSE
    stub.__skoiv_stub__ = True  # type: ignore[attr-defined]
    sys.modules["fuse"] = stub
    return True


def _ensure_libusb() -> None:
    """Make sure pyusb can load a libusb shared library.

    pyusb resolves libusb itself and has no hook for relocated binaries, so we
    seed pyusb's backend cache with the copy vendored by ``libusb-package``
    (shipped inside the frozen Windows worker). This covers mtkclient's own
    USB calls as well as ours.
    """
    try:
        import usb.backend  # noqa: PLC0415

        if usb.backend.get_backend() is not None:
            return  # system libusb already works
    except Exception:  # noqa: BLE001 - fall through to the vendored copy
        pass

    try:
        import libusb_package  # noqa: PLC0415
        import usb.backend  # noqa: PLC0415
    except ImportError as exc:
        raise AdapterError(
            "libusb is not available and libusb-package is not installed. "
            "Install the device extra (uv sync --extra device)."
        ) from exc

    try:
        backend = libusb_package.get_libusb1_backend()
    except Exception as exc:  # noqa: BLE001 - normalize loader failures
        raise AdapterError(f"could not load the vendored libusb library: {exc}") from exc
    if backend is None:
        raise AdapterError("no libusb shared library found (libusb-package returned nothing)")
    usb.backend._backend = backend  # noqa: SLF001 - the supported cache slot


def _import_mtkclient() -> tuple[Any, Any, Any]:
    """Import mtkclient entry points lazily with a helpful error."""
    _ensure_fuse_importable()
    try:
        from mtkclient.Library.DA.mtk_da_handler import DaHandler  # noqa: PLC0415
        from mtkclient.Library.mtk_class import Mtk  # noqa: PLC0415
        from mtkclient.config.mtk_config import MtkConfig  # noqa: PLC0415
    except ImportError as exc:
        raise AdapterError(
            "mtkclient is not installed. Install the device extra "
            "(uv sync --extra device) or run with --adapter mock."
        ) from exc
    return MtkConfig, Mtk, DaHandler


def _load_usb_ids() -> dict[int, dict[int, Any]]:
    try:
        from mtkclient.config.usb_ids import default_ids  # noqa: PLC0415
    except ImportError:
        return _FALLBACK_USB_IDS
    return default_ids


class MtkClientAdapter(DeviceAdapter):
    name = "mtkclient"

    def __init__(self, loglevel: int = logging.WARNING) -> None:
        self._loglevel = loglevel

    def info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "name": self.name,
            "mode": "device",
            "read_only": True,
            "description": "Real MediaTek device access through mtkclient (read-only in 0.1).",
        }
        try:
            import mtkclient  # noqa: F401
            from importlib import metadata

            info["mtkclient_version"] = metadata.version("mtkclient")
        except Exception:  # noqa: BLE001 - version reporting must never break the worker
            info["mtkclient_version"] = None
        return info

    def detect(self) -> list[DetectedDevice]:
        """Enumerate USB devices matching known MediaTek vendor/product ids."""
        _ensure_libusb()
        try:
            import usb.core  # noqa: PLC0415
            import usb.util  # noqa: PLC0415
        except ImportError as exc:
            raise AdapterError(
                "pyusb is required for device detection (installed with the device extra)."
            ) from exc

        known = _load_usb_ids()
        found: list[DetectedDevice] = []
        try:
            all_devices = list(usb.core.find(find_all=True))
        except usb.core.NoBackendError as exc:
            raise AdapterError(
                "libusb is not available. On Windows, libusb-1.0.dll must ship next "
                "to the worker (bundled with the release) and the device must be bound "
                "to WinUSB/libusbK (e.g. via Zadig)."
            ) from exc
        for dev in all_devices:
            vid = int(dev.idVendor)
            pid = int(dev.idProduct)
            if vid not in known or pid not in known[vid]:
                continue
            note = known[vid][pid]
            label = note if isinstance(note, str) else "MediaTek interface"
            mode = "brom" if pid == 0x0003 and vid == 0x0E8D else "preloader"
            try:
                serial = usb.util.get_string(dev, dev.iSerialNumber) or ""
            except Exception:  # noqa: BLE001 - serial strings are often blocked
                serial = ""
            found.append(
                DetectedDevice(
                    port=f"usb:{dev.bus:03d}-{dev.address:03d}",
                    description=label + (f" (serial {serial})" if serial else ""),
                    chip_hint=None,
                    mode=mode,
                    vid=vid,
                    pid=pid,
                )
            )
        return found

    def read_user_area(self, start_lba: int, sector_count: int) -> RawDiskImage:
        """Read raw sectors through the mtkclient DA loader (read-only)."""
        if start_lba < 0 or sector_count <= 0:
            raise AdapterError("invalid read range")

        # mtkclient's connect() blocks forever waiting for a device; fail fast
        # with a clear message when nothing is attached.
        if not self.detect():
            raise AdapterError(
                "no MediaTek target detected. Connect the device in BROM/preloader mode "
                "before reading."
            )

        # Extra safety net: run the blocking handshake/read in a worker thread
        # with a hard timeout so the IPC loop can never wedge.
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._read_user_area_blocking, start_lba, sector_count)
            try:
                return future.result(timeout=120)
            except TimeoutError as exc:
                raise AdapterError(
                    "device operation timed out after 120s (handshake stalled?)"
                ) from exc

    def _read_user_area_blocking(self, start_lba: int, sector_count: int) -> RawDiskImage:
        MtkConfig, Mtk, DaHandler = _import_mtkclient()
        _ensure_libusb()

        config = MtkConfig(loglevel=self._loglevel, gui=None, guiprogress=None)
        mtk = Mtk(config=config, loglevel=self._loglevel, serialportname=None)
        da_handler = DaHandler(mtk, self._loglevel)
        try:
            mtk = da_handler.connect(mtk, ".")
            if mtk is None:
                raise AdapterError("device handshake failed (is a MediaTek target connected?)")
            mtk = da_handler.configure_da(mtk)
            pagesize = int(getattr(da_handler.config, "pagesize", 512) or 512)
            data = da_handler.da_rs(
                start=start_lba,
                sectors=sector_count,
                filename="",
                parttype="user",
                display=False,
            )
            if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
                raise AdapterError("DA read returned no data")
            return RawDiskImage(
                data=bytes(data),
                source="device:mtkclient",
                sector_size=pagesize,
                meta={
                    "adapter": self.name,
                    "start_lba": start_lba,
                    "sector_count": sector_count,
                    "pagesize": pagesize,
                },
            )
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize upstream failures
            raise AdapterError(f"mtkclient read failed: {exc}") from exc
        finally:
            try:
                port = getattr(mtk, "port", None)
                close = getattr(port, "close", None)
                if callable(close):
                    close()
            except Exception:  # noqa: BLE001 - never fail during cleanup
                pass
