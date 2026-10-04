"""Adapter boundary for device access (ADR-0006).

All mtkclient interactions live behind this contract so the rest of the
Workbench depends on Workbench-owned operation semantics, not upstream
internals. The 0.1 line is read-only (ADR-0007).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


class AdapterError(RuntimeError):
    """Raised when a device operation fails or is unavailable."""


@dataclass
class DetectedDevice:
    port: str
    description: str
    chip_hint: str | None = None
    mode: str | None = None  # "brom" | "preloader" | "da" | unknown
    vid: int | None = None
    pid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "description": self.description,
            "chip_hint": self.chip_hint,
            "mode": self.mode,
            "vid": self.vid,
            "pid": self.pid,
        }


@dataclass
class RawDiskImage:
    """Raw bytes read from a device or fixture, with provenance metadata."""

    data: bytes
    source: str
    sector_size: int = 512
    meta: dict[str, Any] = field(default_factory=dict)


class DeviceAdapter(ABC):
    """Read-only device contract for version 0.1.

    Write/servicing methods exist for the operation engine; adapters that
    cannot perform them raise AdapterError. Version 0.1 UI exposes them only
    through the safety engine (plan -> confirm -> execute -> verify).
    """

    name: str = "abstract"

    @abstractmethod
    def info(self) -> dict[str, Any]:
        """Return adapter identity and capability flags."""

    @abstractmethod
    def detect(self) -> list[DetectedDevice]:
        """Enumerate connected MediaTek targets."""

    @abstractmethod
    def read_user_area(self, start_lba: int, sector_count: int) -> RawDiskImage:
        """Read raw sectors from the user area. Read-only."""

    def read_gpt_image(self, sector_size: int = 512) -> RawDiskImage:
        """Default GPT read: protective MBR + header + entry array (LBA 0..33)."""
        return self.read_user_area(0, 34)

    # -- partition level ---------------------------------------------------

    def read_partition(self, name: str) -> RawDiskImage:
        raise AdapterError(f"partition read not supported by adapter {self.name}")

    def write_partition(self, name: str, data: bytes) -> None:
        raise AdapterError(f"partition write not supported by adapter {self.name}")

    def erase_partition(self, name: str) -> None:
        raise AdapterError(f"partition erase not supported by adapter {self.name}")

    # -- servicing primitives ---------------------------------------------

    def seccfg_set(self, lockflag: int) -> str:
        raise AdapterError(f"seccfg not supported by adapter {self.name}")

    def imei_read(self) -> dict[str, Any]:
        raise AdapterError(f"imei read not supported by adapter {self.name}")

    def imei_write(self, imei1: str, imei2: str | None = None) -> dict[str, Any]:
        raise AdapterError(f"imei write not supported by adapter {self.name}")

    # -- connection lifecycle ---------------------------------------------

    @contextmanager
    def session(self):
        """Keep the device session open across a multi-step operation."""
        yield self
