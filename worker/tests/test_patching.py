"""Tests for the patching primitives (modem cert, vbmeta, IMEI/NVItem codec)."""

from __future__ import annotations

import pytest

from skoiv_worker.patching import (
    NVITEM_IMEI_SIZE,
    NVITEM_RECORD_SIZE,
    VENDOR_MODULUS_XIAOMI,
    PatchError,
    calc_checksum,
    decode_imei,
    decode_nvitem_imeis,
    encode_imei,
    find_nvitem_block,
    is_luhn_valid,
    modulus_from_pem,
    patch_md1img,
    patch_nvitem_imeis,
    patch_vbmeta_flags,
    NVITEM_LDI_MARKER,
)

NEW_MODULUS = bytes(range(256))  # distinct 256-byte replacement


def make_md1img() -> bytes:
    return b"MD1HDR" + b"\x00" * 100 + VENDOR_MODULUS_XIAOMI + b"TAIL" * 10


class TestPatchMd1img:
    def test_swaps_vendor_modulus(self):
        img = make_md1img()
        result = patch_md1img(img, NEW_MODULUS)
        assert result.changed
        assert result.offset == img.find(VENDOR_MODULUS_XIAOMI)
        assert result.patched.find(NEW_MODULUS) == result.offset
        assert VENDOR_MODULUS_XIAOMI not in result.patched
        assert len(result.patched) == len(img)

    def test_no_modulus_no_change(self):
        result = patch_md1img(b"just a modem image", NEW_MODULUS)
        assert not result.changed

    def test_rejects_wrong_size_modulus(self):
        with pytest.raises(PatchError):
            patch_md1img(make_md1img(), b"\x01" * 128)

    def test_rejects_vendor_modulus_as_replacement(self):
        with pytest.raises(PatchError, match="nothing to patch"):
            patch_md1img(make_md1img(), VENDOR_MODULUS_XIAOMI)


class TestModulusFromPem:
    def test_roundtrip_from_generated_key(self):
        from Crypto.PublicKey import RSA

        key = RSA.generate(2048)
        pem = key.export_key().decode()
        modulus = modulus_from_pem(pem)
        assert modulus == key.n.to_bytes(256, "big")

    def test_public_pem(self):
        from Crypto.PublicKey import RSA

        key = RSA.generate(2048)
        pem = key.publickey().export_key().decode()
        assert modulus_from_pem(pem) == key.n.to_bytes(256, "big")

    def test_rejects_garbage(self):
        with pytest.raises(PatchError):
            modulus_from_pem("not a pem at all")


class TestPatchVbmeta:
    def test_sets_flags_big_endian(self):
        vb = bytearray(512)
        vb[0:4] = b"AVB0"
        result = patch_vbmeta_flags(bytes(vb), 3)
        assert result.changed
        assert result.patched[0x78:0x7C] == (3).to_bytes(4, "big")

    def test_idempotent(self):
        vb = bytearray(512)
        vb[0:4] = b"AVB0"
        once = patch_vbmeta_flags(bytes(vb), 3)
        twice = patch_vbmeta_flags(once.patched, 3)
        assert not twice.changed

    def test_rejects_non_vbmeta(self):
        with pytest.raises(PatchError, match="AVB0"):
            patch_vbmeta_flags(b"\x00" * 512, 3)

    def test_rejects_bad_mode(self):
        vb = bytearray(512)
        vb[0:4] = b"AVB0"
        with pytest.raises(PatchError):
            patch_vbmeta_flags(bytes(vb), 9)


class TestImeiCodec:
    def test_encode_decode_roundtrip(self):
        imei = "490154203237518"
        assert decode_imei(encode_imei(imei)) == imei

    def test_luhn(self):
        assert is_luhn_valid("490154203237518")
        assert is_luhn_valid("356938035643809")
        assert not is_luhn_valid("490154203237519")

    def test_calc_checksum_stable(self):
        rec = b"\x01" * NVITEM_IMEI_SIZE + b"\x00" * (NVITEM_RECORD_SIZE - NVITEM_IMEI_SIZE)
        c1 = calc_checksum(rec, NVITEM_IMEI_SIZE)
        c2 = calc_checksum(rec, NVITEM_IMEI_SIZE)
        assert c1 == c2 and len(c1) == 8

    def test_nvitem_roundtrip(self):
        imei1, imei2 = "490154203237518", "356938035643809"
        block = bytearray(0x180)
        patched = patch_nvitem_imeis(bytes(block), imei1, imei2)
        assert decode_nvitem_imeis(patched) == [imei1, imei2]

    def test_nvitem_rejects_bad_imei(self):
        block = bytearray(0x180)
        with pytest.raises(PatchError):
            patch_nvitem_imeis(bytes(block), "123456789012345")  # bad Luhn

    def test_find_nvitem_block(self):
        nvdata = b"\x00" * 32 + NVITEM_LDI_MARKER + b"\x00" * 16
        assert find_nvitem_block(nvdata) == 32
        assert find_nvitem_block(b"empty") == -1
