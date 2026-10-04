"""GUID Partition Table parsing with evidence capture and risk classification.

Implements the on-disk GPT layout (UEFI spec) for 512-byte and 4096-byte
sector devices. Every parse result carries the SHA-256 of the raw bytes it
was derived from, per the project evidence policy (ADR-0009).
"""

from __future__ import annotations

import hashlib
import struct
import uuid
import zlib
from dataclasses import dataclass, field
from typing import Any

GPT_SIGNATURE = b"EFI PART"

# Well-known partition type GUIDs (lowercase strings).
TYPE_GUID_NAMES: dict[str, str] = {
    "c12a7328-f81f-11d2-ba4b-00a0c93ec93b": "EFI System",
    "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7": "Microsoft Basic Data",
    "0fc63daf-8483-4772-8e79-3d69d8477de4": "Linux Filesystem",
    "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f": "Linux Swap",
    "2568845d-2332-4675-bc39-8fa5a4748d15": "Android Bootloader",
    "49a4d17f-93a3-45c1-a0de-f50b2ebe2599": "Android Boot",
    "4177c722-9e92-4aab-8644-43502bfd5506": "Android Recovery",
    "6a24c899-6e10-4b7b-a58c-7d2a67e8d507": "Android Super / Metadata",
    "19a710a2-b3ca-11e4-b075-10604b889dcf": "Android Metadata",
    "8f68cc70-c9a3-4c5c-a2b0-b0e9d1e2c7a1": "MediaTek preloader (vendor)",
}

# Partition names that the safety model treats as boot-critical (red).
RED_EXACT = {
    "preloader",
    "pgpt",
    "sgpt",
    "lk",
    "lk2",
    "boot",
    "recovery",
    "vbmeta",
    "vbmeta_system",
    "vbmeta_vendor",
    "tee1",
    "tee2",
    "sspm_1",
    "sspm_2",
    "spmfw",
    "gz1",
    "gz2",
    "mcupm_1",
    "mcupm_2",
    "md1img",
    "spm",
}
RED_PREFIXES = ("preloader", "lk", "tee", "sspm", "spmfw", "gz", "mcupm", "md1")

# Partitions that damage device identity / calibration if corrupted (yellow).
YELLOW_EXACT = {
    "nvram",
    "nvdata",
    "nvcfg",
    "proinfo",
    "protect1",
    "protect2",
    "persist",
    "seccfg",
    "expdb",
    "frp",
    "metadata",
    "para",
    "flashinfo",
    "otp",
    "efuse",
}


class GptError(ValueError):
    """Raised when bytes cannot be interpreted as a GPT disk."""


@dataclass
class GptPartition:
    index: int
    name: str
    type_guid: str
    type_name: str
    unique_guid: str
    first_lba: int
    last_lba: int
    sectors: int
    size_bytes: int
    attributes: int
    risk: str  # "green" | "yellow" | "red"

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "type_guid": self.type_guid,
            "type_name": self.type_name,
            "unique_guid": self.unique_guid,
            "first_lba": self.first_lba,
            "last_lba": self.last_lba,
            "sectors": self.sectors,
            "size_bytes": self.size_bytes,
            "attributes": self.attributes,
            "risk": self.risk,
        }


@dataclass
class GptTable:
    sector_size: int
    disk_guid: str
    current_lba: int
    backup_lba: int
    first_usable_lba: int
    last_usable_lba: int
    num_partition_entries: int
    size_of_partition_entry: int
    header_crc32_ok: bool
    entries_crc32_ok: bool
    partitions: list[GptPartition] = field(default_factory=list)
    raw_sha256: str = ""
    raw_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sector_size": self.sector_size,
            "disk_guid": self.disk_guid,
            "current_lba": self.current_lba,
            "backup_lba": self.backup_lba,
            "first_usable_lba": self.first_usable_lba,
            "last_usable_lba": self.last_usable_lba,
            "num_partition_entries": self.num_partition_entries,
            "size_of_partition_entry": self.size_of_partition_entry,
            "header_crc32_ok": self.header_crc32_ok,
            "entries_crc32_ok": self.entries_crc32_ok,
            "partitions": [p.to_dict() for p in self.partitions],
            "raw_sha256": self.raw_sha256,
            "raw_size": self.raw_size,
        }


def classify_partition_risk(name: str) -> str:
    lowered = name.strip().lower()
    if lowered in RED_EXACT or any(lowered.startswith(p) for p in RED_PREFIXES):
        return "red"
    if lowered in YELLOW_EXACT:
        return "yellow"
    if lowered in ("system", "system_ext", "vendor", "product", "cache", "userdata", "intsd", "logo", "odmdtbo"):
        return "green"
    # Conservative default: unknown partitions are treated with care.
    return "yellow"


def _guid_str(raw16: bytes) -> str:
    return str(uuid.UUID(bytes_le=bytes(raw16)))


def parse_gpt(raw: bytes, sector_size: int = 512) -> GptTable:
    """Parse the GPT from raw disk bytes starting at LBA 0.

    ``raw`` must include at least the MBR sector, the header sector, and the
    partition entry array (typically LBA 0..33 for 512-byte sectors).
    """
    if sector_size not in (512, 4096):
        raise GptError(f"unsupported sector size: {sector_size}")

    header_offset = sector_size
    minimum = sector_size * 2 + 128 * 128  # MBR + header + 128 entries
    if len(raw) < header_offset + 92:
        raise GptError(f"raw image too small for a GPT header: {len(raw)} bytes")
    if len(raw) < minimum:
        # Tolerate shorter entry arrays but require at least one entry block.
        minimum = sector_size * 2 + 128

    header = raw[header_offset : header_offset + 92]
    if header[0:8] != GPT_SIGNATURE:
        raise GptError("missing GPT signature (bytes are not a GUID partition table)")

    (
        _sig,
        revision,
        header_size,
        header_crc,
        _reserved,
        current_lba,
        backup_lba,
        first_usable,
        last_usable,
        disk_guid_raw,
        entries_start_lba,
        num_entries,
        entry_size,
        entries_crc,
    ) = struct.unpack("<8sIIIIQQQQ16sQIII", header)

    if revision != 0x00010000:
        raise GptError(f"unsupported GPT revision: 0x{revision:08x}")
    if not (92 <= header_size <= sector_size):
        raise GptError(f"implausible GPT header size: {header_size}")
    if entry_size < 128 or entry_size > 4096:
        raise GptError(f"implausible partition entry size: {entry_size}")

    # Verify the header CRC (computed over header_size bytes with the CRC field zeroed).
    crc_region = bytearray(raw[header_offset : header_offset + header_size])
    crc_region[16:20] = b"\x00\x00\x00\x00"
    header_crc_ok = (zlib.crc32(bytes(crc_region)) & 0xFFFFFFFF) == header_crc

    entries_offset = entries_start_lba * sector_size
    entries_bytes_len = num_entries * entry_size
    if entries_offset < 0 or entries_offset + entries_bytes_len > len(raw):
        available = max(0, len(raw) - entries_offset)
        num_entries = available // entry_size
        entries_bytes_len = num_entries * entry_size
    entries_raw = raw[entries_offset : entries_offset + entries_bytes_len]
    entries_crc_ok = (zlib.crc32(entries_raw) & 0xFFFFFFFF) == entries_crc

    partitions: list[GptPartition] = []
    for i in range(num_entries):
        entry = entries_raw[i * entry_size : (i + 1) * entry_size]
        type_raw = entry[0:16]
        if type_raw == b"\x00" * 16:
            continue  # unused entry
        unique_raw = entry[16:32]
        first_lba, last_lba, attributes = struct.unpack("<QQQ", entry[32:56])
        name_raw = entry[56 : min(entry_size, 128)]
        name = name_raw.decode("utf-16-le", errors="replace").rstrip("\x00")
        if last_lba < first_lba:
            raise GptError(f"partition entry {i} has inverted LBA range")
        type_guid = _guid_str(type_raw)
        sectors = last_lba - first_lba + 1
        partitions.append(
            GptPartition(
                index=i,
                name=name,
                type_guid=type_guid,
                type_name=TYPE_GUID_NAMES.get(type_guid, "Unknown"),
                unique_guid=_guid_str(unique_raw),
                first_lba=first_lba,
                last_lba=last_lba,
                sectors=sectors,
                size_bytes=sectors * sector_size,
                attributes=attributes,
                risk=classify_partition_risk(name),
            )
        )

    return GptTable(
        sector_size=sector_size,
        disk_guid=_guid_str(disk_guid_raw),
        current_lba=current_lba,
        backup_lba=backup_lba,
        first_usable_lba=first_usable,
        last_usable_lba=last_usable,
        num_partition_entries=num_entries,
        size_of_partition_entry=entry_size,
        header_crc32_ok=header_crc_ok,
        entries_crc32_ok=entries_crc_ok,
        partitions=partitions,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        raw_size=len(raw),
    )
