"""Binary patching helpers for servicing operations.

patch_md1img is an evidence-preserving reimplementation of the approach used
by bkerler/mtkclient (GPLv3, mtkclient/Library/mtk_crypto.py: patch_md1img):
the Download-Agent-signed modem image embeds a vendor RSA public modulus that
authorizes CERT files; replacing that modulus with an operator-supplied key
allows cert-based baseband repair. Skoiv wraps the same byte-level patch with
mandatory backups and read-back verification at the service layer.

The known vendor modulus constant below originates from mtkclient (GPL-3.0)
and is reproduced with attribution; this project is GPL-3.0-only.
"""

from __future__ import annotations

from dataclasses import dataclass

# Vendor RSA-2048 modulus (big-endian bytes) known to sign CERT structures in
# md1img (attributed: bkerler/mtkclient mtk_crypto.py, "xiaomi modulus").
VENDOR_MODULUS_XIAOMI = bytes(
    [
        0xC0, 0x76, 0x21, 0xF1, 0x95, 0x51, 0x14, 0x2D, 0x3D, 0x5D, 0x9D, 0xD5, 0x14, 0x05, 0xD5, 0xD8,
        0x34, 0x70, 0xD5, 0x41, 0x7E, 0x66, 0x1C, 0xB3, 0xF5, 0x47, 0x2D, 0x2E, 0x4A, 0x9A, 0xE5, 0x63,
        0x45, 0xBF, 0x41, 0x87, 0x16, 0xFE, 0x7F, 0xB5, 0xA5, 0xC0, 0x41, 0x0E, 0x0F, 0xB1, 0x06, 0x72,
        0x59, 0x23, 0x05, 0xAC, 0x46, 0xC1, 0xB8, 0x01, 0x24, 0x06, 0xDD, 0x02, 0x8B, 0xF6, 0x68, 0x7F,
        0x39, 0xDC, 0x5C, 0xAF, 0x45, 0x82, 0x9A, 0xE0, 0x6F, 0x17, 0x58, 0x94, 0xC2, 0x0A, 0xE3, 0x5A,
        0x33, 0x3B, 0x71, 0x9D, 0x96, 0xA5, 0xD7, 0x7F, 0x85, 0x20, 0x66, 0xA8, 0xFF, 0x17, 0xCA, 0xFC,
        0x22, 0x53, 0x89, 0xC0, 0x15, 0x14, 0x92, 0xE0, 0x7F, 0x67, 0xC8, 0x82, 0xB8, 0x9D, 0x13, 0x97,
        0xF9, 0xB5, 0x6A, 0xC2, 0xE5, 0x72, 0xCB, 0x07, 0xC1, 0xCC, 0xF5, 0xD2, 0xFC, 0x59, 0x07, 0x04,
        0x37, 0xDC, 0xBB, 0x35, 0x1C, 0xE0, 0xB6, 0x3D, 0x6C, 0x76, 0x2B, 0x42, 0x7E, 0xB6, 0x6C, 0x90,
        0xD9, 0x3F, 0x6F, 0x2C, 0xCB, 0x66, 0xD4, 0xEF, 0xF2, 0x63, 0xC0, 0xDA, 0x77, 0x35, 0x5B, 0x9E,
        0xE4, 0x02, 0x6F, 0x0C, 0x80, 0x56, 0x9A, 0x19, 0xB8, 0x39, 0xD3, 0x98, 0x8F, 0x4B, 0x55, 0xB0,
        0x42, 0xE7, 0xB9, 0x77, 0x30, 0x84, 0x8F, 0xA6, 0x2D, 0xCA, 0x42, 0x72, 0x02, 0x76, 0xC6, 0x1C,
        0xC3, 0xB6, 0x98, 0x16, 0x4E, 0xE7, 0x41, 0x9B, 0xD1, 0x38, 0xB8, 0x5C, 0xAE, 0x04, 0x21, 0x74,
        0xA7, 0x49, 0x38, 0x19, 0xC8, 0x33, 0x95, 0x3A, 0x4F, 0x93, 0x06, 0x8F, 0xF5, 0x65, 0x1F, 0x31,
        0x63, 0x3A, 0x2A, 0xDB, 0xD1, 0xFB, 0x5F, 0xD8, 0xD6, 0xDD, 0x0E, 0xBF, 0xB3, 0x56, 0x16, 0x6E,
        0xB3, 0x31, 0xBD, 0xE5, 0x8D, 0x1E, 0x22, 0x84, 0xA0, 0x47, 0xC4, 0x42, 0x06, 0x2C, 0x1E, 0xB5,
    ]
)

# Media/vendor moduli can vary; the known set is extended over time with
# evidence-backed entries. Each entry: (label, modulus bytes).
KNOWN_VENDOR_MODULI: list[tuple[str, bytes]] = [("vendor-xiaomi-2048", VENDOR_MODULUS_XIAOMI)]

# AVB vbmeta image header: magic "AVB0"; flags live at byte 0x78 (120) of the
# 256-byte header (AVB_VBMETA_IMAGE_FLAGS, big-endian), same as mtkclient's
# patch_vbmeta (DISABLE_VERITY=1, DISABLE_VERIFICATION=2).
_VBMETA_MAGIC = b"AVB0"
_VBMETA_FLAGS_OFFSET = 0x78
AVB_FLAG_DISABLE_VERITY = 1
AVB_FLAG_DISABLE_VERIFICATION = 2


class PatchError(ValueError):
    """Raised when a patch cannot be applied safely."""


@dataclass
class PatchResult:
    patched: bytes
    changed: bool
    detail: str
    offset: int | None = None
    label: str | None = None


def modulus_from_pem(pem_text: str) -> bytes:
    """Extract a 2048-bit RSA modulus (big-endian, 256 bytes) from a PEM key.

    Accepts public or private PEM. Uses pycryptodome when available and
    falls back to a minimal ASN.1 scan of the modulus INTEGER.
    """
    try:
        from Crypto.PublicKey import RSA  # noqa: PLC0415

        key = RSA.import_key(pem_text)
        n = key.n
        return n.to_bytes(256, "big")
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 - normalize key parse failures
        raise PatchError(f"could not parse PEM key: {exc}") from exc

    # Minimal fallback: find the 256-byte modulus inside DER (look for the
    # 0x02 0x82 0x01 0x01 INTEGER header followed by 256 bytes).
    import base64  # noqa: PLC0415
    import re  # noqa: PLC0415

    b64 = re.sub(r"-----[^-]+-----|\s", "", pem_text)
    try:
        der = base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        raise PatchError(f"could not decode PEM data: {exc}") from exc
    marker = b"\x02\x82\x01\x01"
    idx = der.find(marker)
    if idx == -1:
        raise PatchError("no RSA-2048 modulus found in PEM")
    cand = der[idx + 4 : idx + 4 + 256]
    if len(cand) == 256:
        return cand
    raise PatchError("PEM modulus is not 2048-bit")


def patch_md1img(md1img: bytes, new_modulus: bytes) -> PatchResult:
    """Replace the vendor cert-verification modulus inside a modem image."""
    if len(new_modulus) != 256:
        raise PatchError("replacement modulus must be 256 bytes (RSA-2048)")
    if new_modulus in (m for _, m in KNOWN_VENDOR_MODULI):
        raise PatchError("replacement modulus equals the vendor modulus - nothing to patch")

    for label, old in KNOWN_VENDOR_MODULI:
        idx = md1img.find(old)
        if idx != -1:
            patched = bytearray(md1img)
            patched[idx : idx + 256] = new_modulus
            return PatchResult(
                patched=bytes(patched),
                changed=True,
                detail=f"replaced {label} cert modulus at offset 0x{idx:x}",
                offset=idx,
                label=label,
            )
    return PatchResult(
        patched=md1img,
        changed=False,
        detail="no known vendor cert modulus found in image (patch not applied)",
    )


def patch_vbmeta_flags(vbmeta: bytes, vbmode: int = 3) -> PatchResult:
    """Patch AVB vbmeta verification flags (mtkclient-compatible semantics).

    vbmode bits: 1 = disable verity, 2 = disable verification, 3 = both,
    0 = re-enable. The flags word is replaced (not OR-ed) exactly like
    mtkclient's patch_vbmeta.
    """
    if not vbmeta.startswith(_VBMETA_MAGIC):
        raise PatchError("not an AVB vbmeta image (missing AVB0 magic)")
    if vbmode < 0 or vbmode > 3:
        raise PatchError("vbmode must be 0..3")

    patched = bytearray(vbmeta)
    current = patched[_VBMETA_FLAGS_OFFSET : _VBMETA_FLAGS_OFFSET + 4]
    patched[_VBMETA_FLAGS_OFFSET : _VBMETA_FLAGS_OFFSET + 4] = int.to_bytes(vbmode, 4, "big")
    if patched[_VBMETA_FLAGS_OFFSET : _VBMETA_FLAGS_OFFSET + 4] == current:
        return PatchResult(patched=bytes(patched), changed=False, detail="flags already set")
    return PatchResult(
        patched=bytes(patched),
        changed=True,
        detail=(
            f"vbmeta flags {current.hex()} -> {vbmode.to_bytes(4, 'big').hex()} "
            f"(vbmode={vbmode})"
        ),
        offset=_VBMETA_FLAGS_OFFSET,
    )


# ---------------------------------------------------------------------------
# IMEI / NVItem codec (attributed: bkerler/mtkclient mtk_crypto.py, GPL-3.0)
# ---------------------------------------------------------------------------

def luhn_checksum(card_number: str) -> int:
    digits = [int(d) for d in str(card_number)]
    odd = digits[-1::-2]
    even = digits[-2::-2]
    total = sum(odd)
    for d in even:
        d2 = d * 2
        total += (d2 // 10 + d2 % 10) if d2 > 9 else d2
    return total % 10


def is_luhn_valid(card_number: str) -> bool:
    return luhn_checksum(card_number) == 0


def calc_checksum(data: bytes, itemsize: int) -> bytes:
    import hashlib

    h = bytearray(hashlib.md5(data[:itemsize]).digest())
    for i in range(8):
        h[i] = h[i] ^ h[i + 8]
    return bytes(h[:8])


def decode_imei(data: bytes) -> str:
    imei = ""
    data = bytearray(data)
    for x in range(8):
        imei += "%0x" % (data[x] & 0xF)
        val = (data[x] & 0xF0) >> 4
        if val == 0xF:
            break
        imei += "%0x" % val
    return imei[:15]


def encode_imei(imei: str) -> bytes:
    data = imei[:15] + "F"
    out = b""
    for x in range(0, 16, 2):
        v = int(data[x], 16) + (int(data[x + 1], 16) << 4)
        out += int.to_bytes(v, 1, "little")
    return out


# nvdata NVItem block: LDI marker then 0x180-byte record area; each 0x20
# record = 10B encoded IMEI + 8B checksum + padding (mtkclient semantics).
NVITEM_LDI_MARKER = b"\x4C\x44\x49\x00\x10\xEF\x0A\x00\x0A"
NVITEM_BLOCK_SIZE = 0x180
NVITEM_RECORD_SIZE = 0x20
NVITEM_IMEI_SIZE = 0x0A
NVITEM_CSUM_SIZE = 0x08


def find_nvitem_block(nvdata: bytes) -> int:
    return nvdata.find(NVITEM_LDI_MARKER)


def decode_nvitem_imeis(block: bytes) -> list[str]:
    """Decode all Luhn-valid IMEI records from a decrypted nvitem block."""
    out: list[str] = []
    for i in range(len(block) // NVITEM_RECORD_SIZE):
        rec = block[i * NVITEM_RECORD_SIZE : (i + 1) * NVITEM_RECORD_SIZE]
        if rec[:NVITEM_IMEI_SIZE] == b"\xFF" * NVITEM_IMEI_SIZE:
            continue
        if calc_checksum(rec, NVITEM_IMEI_SIZE) == rec[NVITEM_IMEI_SIZE : NVITEM_IMEI_SIZE + NVITEM_CSUM_SIZE]:
            imei = decode_imei(rec[:NVITEM_IMEI_SIZE])
            if imei and is_luhn_valid(imei):
                out.append(imei)
    return out


def patch_nvitem_imeis(block: bytes, imei1: str, imei2: str | None = None) -> bytes:
    """Return the block with its first two IMEI records replaced."""
    for imei in [imei1] + ([imei2] if imei2 else []):
        if len(imei) != 15 or not imei.isdigit() or not is_luhn_valid(imei):
            raise PatchError(f"IMEI {imei!r} must be 15 digits with a valid Luhn checksum")
    patched = bytearray(block)
    slot = 0
    for imei in [imei1] + ([imei2] if imei2 else []):
        rec = bytearray(NVITEM_RECORD_SIZE)
        rec[:NVITEM_IMEI_SIZE] = encode_imei(imei)
        rec[NVITEM_IMEI_SIZE : NVITEM_IMEI_SIZE + NVITEM_CSUM_SIZE] = calc_checksum(
            rec, NVITEM_IMEI_SIZE
        )
        patched[slot * NVITEM_RECORD_SIZE : (slot + 1) * NVITEM_RECORD_SIZE] = rec
        slot += 1
    return bytes(patched)
