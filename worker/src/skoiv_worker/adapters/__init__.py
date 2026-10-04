"""Device adapters. See base.py for the Workbench-owned contract (ADR-0006)."""

from __future__ import annotations

import os

from .base import AdapterError, DetectedDevice, DeviceAdapter, RawDiskImage
from .mock import MockAdapter
from .mtkclient_adapter import MtkClientAdapter

__all__ = [
    "AdapterError",
    "DetectedDevice",
    "DeviceAdapter",
    "MockAdapter",
    "MtkClientAdapter",
    "RawDiskImage",
    "create_adapter",
]


def _mtkclient_available() -> bool:
    try:
        import mtkclient  # noqa: F401
    except ImportError:
        return False
    return True


def create_adapter(kind: str = "auto") -> DeviceAdapter:
    """Create an adapter.

    ``auto``: mtkclient when installed, otherwise mock (with the choice
    visible in ``adapter.info`` so the UI never lies to the user).
    ``SKOIV_MOCK=1`` forces mock mode regardless of ``kind``.
    """
    if os.environ.get("SKOIV_MOCK") == "1":
        kind = "mock"

    if kind == "mock":
        return MockAdapter()
    if kind == "mtkclient":
        return MtkClientAdapter()
    if kind == "auto":
        return MtkClientAdapter() if _mtkclient_available() else MockAdapter()
    raise AdapterError(f"unknown adapter kind: {kind!r}")
