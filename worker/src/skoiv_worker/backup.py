"""Backup engine: partition backups with SHA-256 manifests and verification.

Backups are the project's core safety mechanism (ADR-0008): every mutating
servicing operation auto-backs-up its targets first, and restores always
verify hashes before and read-back after writing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from .adapters.base import DeviceAdapter
from .safety import SafetyError


class BackupError(RuntimeError):
    pass


@dataclass
class BackupManifest:
    backup_id: str
    created: float
    adapter: str
    source: str
    note: str
    partitions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "created": self.created,
            "adapter": self.adapter,
            "source": self.source,
            "note": self.note,
            "partitions": self.partitions,
        }

    def covers(self, partition: str) -> bool:
        return partition.lower() in self.partitions


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return cleaned or "partition"


class BackupEngine:
    """Filesystem-backed partition backup store.

    Layout: <root>/<backup_id>/manifest.json + <partition>.bin
    """

    def __init__(self, adapter: DeviceAdapter, root: str | None = None, emit=None) -> None:
        self.adapter = adapter
        self.root = root or os.environ.get("SKOIV_BACKUP_ROOT") or os.path.join(os.getcwd(), "backups")
        self._emit = emit or (lambda _msg: None)

    # -- creation ----------------------------------------------------------

    def create(self, partitions: list[str], note: str = "") -> dict[str, Any]:
        if not partitions:
            raise BackupError("no partitions selected for backup")
        ts = time.strftime("%Y%m%d-%H%M%S")
        suffix = secrets.token_hex(2)
        backup_id = f"{ts}-{_safe_name(self.adapter.name)}-{len(partitions)}p-{suffix}"
        path = os.path.join(self.root, backup_id)
        os.makedirs(path, exist_ok=True)

        manifest = BackupManifest(
            backup_id=backup_id,
            created=time.time(),
            adapter=self.adapter.name,
            source="",
            note=note,
        )
        for name in partitions:
            key = name.lower()
            image = self.adapter.read_partition(name)
            manifest.source = manifest.source or image.source
            fname = f"{_safe_name(name)}.bin"
            with open(os.path.join(path, fname), "wb") as fh:
                fh.write(image.data)
            manifest.partitions[key] = {
                "file": fname,
                "size": len(image.data),
                "sha256": _sha256(image.data),
            }

        with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest.to_dict(), fh, indent=2)
        return manifest.to_dict()

    # -- listing / verification -------------------------------------------

    def list(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not os.path.isdir(self.root):
            return out
        for entry in sorted(os.listdir(self.root), reverse=True):
            mf = os.path.join(self.root, entry, "manifest.json")
            if os.path.isfile(mf):
                try:
                    with open(mf, encoding="utf-8") as fh:
                        out.append(json.load(fh))
                except (OSError, json.JSONDecodeError):
                    continue
        return out

    def load_manifest(self, backup_id: str) -> dict[str, Any]:
        mf = os.path.join(self.root, _safe_name(backup_id), "manifest.json")
        if not os.path.isfile(mf):
            raise BackupError(f"backup not found: {backup_id}")
        with open(mf, encoding="utf-8") as fh:
            return json.load(fh)

    def read_backup_file(self, backup_id: str, partition: str) -> bytes:
        manifest = self.load_manifest(backup_id)
        entry = manifest["partitions"].get(partition.lower())
        if entry is None:
            raise BackupError(f"backup {backup_id} does not contain {partition}")
        path = os.path.join(self.root, _safe_name(backup_id), entry["file"])
        with open(path, "rb") as fh:
            return fh.read()

    def verify(self, backup_id: str) -> dict[str, Any]:
        manifest = self.load_manifest(backup_id)
        results = {}
        ok = True
        for name, entry in manifest["partitions"].items():
            try:
                data = self.read_backup_file(backup_id, name)
                good = _sha256(data) == entry["sha256"] and len(data) == entry["size"]
            except (OSError, BackupError):
                good = False
            results[name] = {"ok": good, "sha256": entry["sha256"]}
            ok = ok and good
        return {"backup_id": backup_id, "ok": ok, "partitions": results}

    # -- coverage / restore ------------------------------------------------

    def coverage(self) -> dict[str, str]:
        """Map partition name -> backup id of the newest verified backup."""
        out: dict[str, str] = {}
        for manifest in self.list():
            for name in manifest.get("partitions", {}):
                if name not in out:
                    v = self.verify(manifest["backup_id"])
                    if v["ok"]:
                        out[name] = manifest["backup_id"]
        return out

    def restore(self, backup_id: str, partitions: list[str] | None = None) -> dict[str, Any]:
        """Restore partitions with pre-hash check and read-back verification."""
        manifest = self.load_manifest(backup_id)
        targets = [p.lower() for p in partitions] if partitions else list(manifest["partitions"])
        results = {}
        for name in targets:
            entry = manifest["partitions"].get(name)
            if entry is None:
                raise BackupError(f"backup {backup_id} does not contain {name}")
            data = self.read_backup_file(backup_id, name)
            if _sha256(data) != entry["sha256"]:
                raise SafetyError(f"backup file for {name} failed hash check - restore refused")
            self.adapter.write_partition(name, data)
            readback = self.adapter.read_partition(name)
            verified = _sha256(readback.data) == entry["sha256"]
            results[name] = {
                "restored": True,
                "verified": verified,
                "sha256": entry["sha256"],
            }
        return {"backup_id": backup_id, "restored": results}
