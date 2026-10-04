"""Tests for the backup engine (create/verify/restore round-trips)."""

from __future__ import annotations

import pytest

from skoiv_worker.adapters.mock import MockAdapter
from skoiv_worker.backup import BackupEngine, BackupError


@pytest.fixture()
def engine(tmp_path):
    return BackupEngine(MockAdapter(), root=str(tmp_path / "backups"))


class TestBackupEngine:
    def test_create_manifest_and_files(self, engine):
        manifest = engine.create(["md1img", "vbmeta"], note="test")
        assert set(manifest["partitions"]) == {"md1img", "vbmeta"}
        assert manifest["note"] == "test"
        assert manifest["adapter"] == "mock"
        verified = engine.verify(manifest["backup_id"])
        assert verified["ok"]

    def test_create_empty_rejected(self, engine):
        with pytest.raises(BackupError):
            engine.create([])

    def test_list_and_coverage(self, engine):
        engine.create(["md1img"])
        engine.create(["nvdata"])
        listing = engine.list()
        assert len(listing) == 2
        coverage = engine.coverage()
        assert coverage.get("md1img")
        assert coverage.get("nvdata")

    def test_restore_roundtrip(self, engine):
        adapter = engine.adapter
        original = adapter.read_partition("md1img").data
        manifest = engine.create(["md1img"])
        adapter.write_partition("md1img", b"\x00" * 128)  # corrupt
        assert adapter.read_partition("md1img").data != original

        result = engine.restore(manifest["backup_id"], ["md1img"])
        assert result["restored"]["md1img"]["verified"]
        assert adapter.read_partition("md1img").data == original

    def test_restore_unknown_backup(self, engine):
        with pytest.raises(BackupError):
            engine.restore("no-such-backup")

    def test_restore_unknown_partition(self, engine):
        manifest = engine.create(["md1img"])
        with pytest.raises(BackupError):
            engine.restore(manifest["backup_id"], ["nvdata"])

    def test_verify_detects_corruption(self, engine):
        import os

        manifest = engine.create(["md1img"])
        path = os.path.join(engine.root, manifest["backup_id"], manifest["partitions"]["md1img"]["file"])
        with open(path, "r+b") as fh:
            fh.write(b"\xFF")
        assert not engine.verify(manifest["backup_id"])["ok"]
