"""Adapter boundary for device access (ADR-0006).

All mtkclient interactions live behind this contract so the rest of the
Workbench depends on Workbench-owned operation semantics, not upstream
internals. The 0.1 line is read-only (ADR-0007).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
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
    """Read-only device contract for version 0.1."""

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
