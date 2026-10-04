"""Mock adapter: deterministic fixture device for development and tests.

Generates a synthetic MediaTek-style eMMC layout (protective MBR + GPT +
typical MT6768 partition set) entirely in memory. Used automatically when
mtkclient is not installed, when ``--adapter mock`` is passed, or when
``SKOIV_MOCK=1`` is set. No hardware access occurs in mock mode.
"""

from __future__ import annotations

import struct
import uuid
import zlib
from typing import Any

from .base import DetectedDevice, DeviceAdapter, RawDiskImage

SECTOR = 512

# (name, type_guid, size_mib, attributes)
_MOCK_LAYOUT: list[tuple[str, str, int, int]] = [
    ("preloader", "2568845d-2332-4675-bc39-8fa5a4748d15", 4, 0),
    ("pgpt", "c12a7328-f81f-11d2-ba4b-00a0c93ec93b", 2, 0),
    ("proinfo", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 3, 0),
    ("nvram", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 64, 0),
    ("protect1", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 8, 0),
    ("protect2", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 8, 0),
    ("seccfg", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 4, 0),
    ("persist", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 64, 0),
    ("expdb", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 64, 0),
    ("frp", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 1, 0),
    ("nvcfg", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 20, 0),
    ("metadata", "19a710a2-b3ca-11e4-b075-10604b889dcf", 32, 0),
    ("para", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 8, 0),
    ("md1img", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 64, 0),
    ("spmfw", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 4, 0),
    ("scp1", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 8, 0),
    ("sspm_1", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 8, 0),
    ("gz1", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 16, 0),
    ("lk", "2568845d-2332-4675-bc39-8fa5a4748d15", 2, 0),
    ("lk2", "2568845d-2332-4675-bc39-8fa5a4748d15", 2, 0),
    ("boot", "49a4d17f-93a3-45c1-a0de-f50b2ebe2599", 64, 0),
    ("recovery", "4177c722-9e92-4aab-8644-43502bfd5506", 64, 0),
    ("vbmeta", "c12a7328-f81f-11d2-ba4b-00a0c93ec93b", 8, 0),
    ("logo", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 16, 0),
    ("odmdtbo", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 16, 0),
    ("super", "6a24c899-6e10-4b7b-a58c-7d2a67e8d507", 4096, 0),
    ("cache", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 256, 0),
    ("userdata", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 2048, 0),
    ("flashinfo", "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", 4, 0),
]

_MOCK_DISK_GUID = "9f2c1a4e-7b3d-4c2a-9e10-5d8f6b1c2a70"


def _guid_bytes(guid_str: str) -> bytes:
    return uuid.UUID(guid_str).bytes_le


def _partition_entry(name: str, type_guid: str, first_lba: int, last_lba: int, attributes: int = 0) -> bytes:
    name_utf16 = name.encode("utf-16-le")
    entry = bytearray(128)
    entry[0:16] = _guid_bytes(type_guid)
    entry[16:32] = _guid_bytes(str(uuid.uuid5(uuid.NAMESPACE_URL, f"skoiv-mock:{name}")))
    struct.pack_into("<QQQ", entry, 32, first_lba, last_lba, attributes)
    entry[56 : 56 + min(len(name_utf16), 72)] = name_utf16[:72]
    return bytes(entry)


def build_mock_gpt_image() -> bytes:
    """Build a complete, CRC-valid synthetic GPT image (LBA 0..33)."""
    entry_size = 128
    num_entries = 128
    entries_start_lba = 2
    entries_bytes = bytearray()
    lba_cursor = entries_start_lba + (num_entries * entry_size) // SECTOR  # 34

    for name, type_guid, size_mib, attrs in _MOCK_LAYOUT:
        sectors = (size_mib * 1024 * 1024) // SECTOR
        first = lba_cursor
        last = first + sectors - 1
        entries_bytes += _partition_entry(name, type_guid, first, last, attrs)
        lba_cursor = last + 1

    while len(entries_bytes) < num_entries * entry_size:
        entries_bytes += b"\x00" * entry_size

    total_lbas = lba_cursor + 2048  # trailing slack
    last_usable = total_lbas - 34

    header = bytearray(SECTOR)
    header[0:8] = b"EFI PART"
    struct.pack_into("<I", header, 8, 0x00010000)  # revision
    struct.pack_into("<I", header, 12, 92)  # header size
    # header CRC later at offset 16
    struct.pack_into("<I", header, 20, 0)  # reserved
    struct.pack_into("<Q", header, 24, 1)  # current LBA
    struct.pack_into("<Q", header, 32, total_lbas - 1)  # backup LBA
    struct.pack_into("<Q", header, 40, 34)  # first usable
    struct.pack_into("<Q", header, 48, last_usable)  # last usable
    header[56:72] = _guid_bytes(_MOCK_DISK_GUID)
    struct.pack_into("<Q", header, 72, entries_start_lba)
    struct.pack_into("<I", header, 80, num_entries)
    struct.pack_into("<I", header, 84, entry_size)
    struct.pack_into("<I", header, 88, zlib.crc32(bytes(entries_bytes)) & 0xFFFFFFFF)
    struct.pack_into("<I", header, 16, zlib.crc32(bytes(header[:92])) & 0xFFFFFFFF)

    # Protective MBR: one partition of type 0xEE covering the disk.
    mbr = bytearray(SECTOR)
    part = bytearray(16)  # partition record; status byte 0x00 = bootable flag unused
    struct.pack_into("<I", part, 8, 1)  # start LBA
    struct.pack_into("<I", part, 12, min(total_lbas - 1, 0xFFFFFFFF))
    part[4] = 0xEE
    mbr[446:462] = part
    mbr[510:512] = b"\x55\xaa"

    return bytes(mbr) + bytes(header) + bytes(entries_bytes)


class MockAdapter(DeviceAdapter):
    name = "mock"

    def __init__(self) -> None:
        self._image: bytes | None = None

    def info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "fixture",
            "read_only": True,
            "description": "Deterministic fixture device (no hardware access).",
        }

    def detect(self) -> list[DetectedDevice]:
        return [
            DetectedDevice(
                port="mock:001",
                description="Skoiv fixture device (mock)",
                chip_hint="MT6768",
                mode="brom",
                vid=0x0E8D,
                pid=0x0003,
            )
        ]

    def read_user_area(self, start_lba: int, sector_count: int) -> RawDiskImage:
        if self._image is None:
            self._image = build_mock_gpt_image()
        offset = start_lba * SECTOR
        end = offset + sector_count * SECTOR
        data = self._image[offset:end]
        return RawDiskImage(
            data=data,
            source="mock:fixture",
            sector_size=SECTOR,
            meta={"adapter": self.name, "start_lba": start_lba, "sector_count": sector_count},
        )
