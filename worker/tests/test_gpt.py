"""GPT parser tests against the synthetic fixture image."""

from __future__ import annotations

import struct
import zlib

import pytest

from skoiv_worker.adapters.mock import _MOCK_LAYOUT, build_mock_gpt_image
from skoiv_worker.gpt import GptError, classify_partition_risk, parse_gpt


def test_parse_mock_gpt():
    raw = build_mock_gpt_image()
    table = parse_gpt(raw, sector_size=512)

    assert table.header_crc32_ok is True
    assert table.entries_crc32_ok is True
    assert table.raw_size == len(raw)
    assert len(table.raw_sha256) == 64

    names = [p.name for p in table.partitions]
    assert names == [layout[0] for layout in _MOCK_LAYOUT]
    assert table.disk_guid == "9f2c1a4e-7b3d-4c2a-9e10-5d8f6b1c2a70"

    by_name = {p.name: p for p in table.partitions}
    assert by_name["preloader"].risk == "red"
    assert by_name["boot"].risk == "red"
    assert by_name["nvram"].risk == "yellow"
    assert by_name["userdata"].risk == "green"

    # Partition LBA ranges must be contiguous and non-overlapping.
    ordered = sorted(table.partitions, key=lambda p: p.first_lba)
    for a, b in zip(ordered, ordered[1:]):
        assert a.last_lba < b.first_lba
        assert a.sectors == a.last_lba - a.first_lba + 1
        assert a.size_bytes == a.sectors * 512


def test_raw_sha256_is_stable():
    import hashlib

    raw = build_mock_gpt_image()
    table = parse_gpt(raw)
    assert table.raw_sha256 == hashlib.sha256(raw).hexdigest()


def test_rejects_non_gpt_bytes():
    with pytest.raises(GptError):
        parse_gpt(b"\x00" * 4096)


def test_rejects_short_image():
    with pytest.raises(GptError):
        parse_gpt(b"EFI PART" + b"\x00" * 100)


def test_detects_header_crc_corruption():
    raw = bytearray(build_mock_gpt_image())
    # Flip a reserved field inside the header and leave the CRC stale.
    raw[512 + 20] ^= 0xFF
    table = parse_gpt(bytes(raw))
    assert table.header_crc32_ok is False


def test_detects_entries_crc_corruption():
    raw = bytearray(build_mock_gpt_image())
    raw[1024] ^= 0xFF  # first byte of the first partition entry
    table = parse_gpt(bytes(raw))
    assert table.entries_crc32_ok is False


def test_partition_entry_odd_lba_raises():
    raw = bytearray(build_mock_gpt_image())
    # Corrupt entry 0's LBA range (first > last) without touching name.
    struct.pack_into("<Q", raw, 1024 + 32, 5000)  # first_lba
    struct.pack_into("<Q", raw, 1024 + 40, 100)  # last_lba
    # Fix entries CRC so the structural check triggers instead.
    entries = raw[1024 : 1024 + 128 * 128]
    struct.pack_into("<I", raw, 512 + 88, zlib.crc32(bytes(entries)) & 0xFFFFFFFF)
    struct.pack_into("<I", raw, 512 + 16, 0)
    header = bytearray(raw[512 : 512 + 92])
    struct.pack_into("<I", raw, 512 + 16, zlib.crc32(bytes(header)) & 0xFFFFFFFF)
    with pytest.raises(GptError):
        parse_gpt(bytes(raw))


def test_risk_classification_defaults_conservative():
    assert classify_partition_risk("preloader") == "red"
    assert classify_partition_risk("TEE1") == "red"
    assert classify_partition_risk("nvram") == "yellow"
    assert classify_partition_risk("userdata") == "green"
    assert classify_partition_risk("weird_oem_blob") == "yellow"
