"""End-to-end tests for the two-phase mutation pipeline (plan -> confirm -> execute)."""

from __future__ import annotations

import pytest

from skoiv_worker.adapters.mock import MockAdapter
from skoiv_worker.service import Service
from skoiv_worker.backup import BackupEngine


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("SKOIV_BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setenv("SKOIV_SESSION_ROOT", str(tmp_path / "sessions"))
    service = Service(MockAdapter(), emit=lambda _msg: None)
    return service


def plan_and_token(svc, method, params):
    plan_resp = svc.handle_request("t-plan", method, {"phase": "plan", **params})
    assert plan_resp["ok"], plan_resp
    assert plan_resp["result"]["phase"] == "plan"
    return plan_resp["result"]["plan"], plan_resp["result"]["confirm_token"]


class TestPartitionWrite:
    def test_plan_does_not_mutate(self, svc):
        before = svc.adapter.read_partition("nvdata").data
        plan, token = plan_and_token(svc, "partition.write", {"name": "nvdata", "backup_id": "x"})
        assert plan["risk"] == "yellow"
        assert plan["backup_partitions"] == ["nvdata"]
        assert token
        assert svc.adapter.read_partition("nvdata").data == before

    def test_execute_writes_and_verifies(self, svc):
        payload = b"\xAB" * 256
        plan, token = plan_and_token(
            svc, "partition.write", {"name": "nvdata", "data_hex": payload.hex()}
        )
        resp = svc.handle_request(
            "t-ex",
            "partition.write",
            {
                "phase": "execute",
                "name": "nvdata",
                "data_hex": payload.hex(),
                "confirm_token": token,
            },
        )
        assert resp["ok"], resp
        result = resp["result"]
        assert result["phase"] == "executed"
        assert result["verified"] is True
        assert result["backup_id"]  # auto-backup happened
        assert svc.adapter.read_partition("nvdata").data == payload

    def test_execute_without_token_rejected(self, svc):
        payload = b"\xAB" * 256
        plan_and_token(svc, "partition.write", {"name": "nvdata", "data_hex": payload.hex()})
        resp = svc.handle_request(
            "t-ex",
            "partition.write",
            {"phase": "execute", "name": "nvdata", "data_hex": payload.hex(), "confirm_token": "bad"},
        )
        assert not resp["ok"]
        assert resp["error"]["code"] == "refused-by-safety"

    def test_boot_critical_requires_attestation(self, svc):
        payload = b"\xCD" * 256
        plan, token = plan_and_token(
            svc, "partition.write", {"name": "boot", "data_hex": payload.hex()}
        )
        assert plan["risk"] == "red"
        assert plan["requires_attestation"]
        resp = svc.handle_request(
            "t-ex",
            "partition.write",
            {
                "phase": "execute",
                "name": "boot",
                "data_hex": payload.hex(),
                "confirm_token": token,
                "attestation": True,
                "typed_confirm": "CONFIRM",
            },
        )
        assert resp["ok"], resp

    def test_boot_critical_rejects_missing_typed_confirm(self, svc):
        payload = b"\xCD" * 256
        _, token = plan_and_token(
            svc, "partition.write", {"name": "boot", "data_hex": payload.hex()}
        )
        resp = svc.handle_request(
            "t-ex",
            "partition.write",
            {
                "phase": "execute",
                "name": "boot",
                "data_hex": payload.hex(),
                "confirm_token": token,
                "attestation": True,
            },
        )
        assert not resp["ok"]
        assert resp["error"]["code"] == "refused-by-safety"


class TestBackupRestore:
    def test_restore_red_needs_attestation_and_backup(self, svc):
        manifest = svc.backup.create(["nvdata"])
        payload = b"\x11" * 256
        svc.adapter.write_partition("nvdata", payload)

        plan, token = plan_and_token(
            svc, "backup.restore", {"backup_id": manifest["backup_id"], "phase": "plan"}
        )
        assert plan["risk"] == "red"

        resp = svc.handle_request(
            "t-ex",
            "backup.restore",
            {
                "phase": "execute",
                "backup_id": manifest["backup_id"],
                "confirm_token": token,
                "attestation": True,
                "typed_confirm": "CONFIRM",
            },
        )
        assert resp["ok"], resp
        assert resp["result"]["restored"]["nvdata"]["verified"]
        assert svc.adapter.read_partition("nvdata").data != payload

    def test_restore_without_backups_refused(self, svc, tmp_path, monkeypatch):
        # fresh engine with no backups yet
        plan, token = plan_and_token(
            svc, "backup.restore", {"backup_id": "ghost", "phase": "plan"}
        )
        resp = svc.handle_request(
            "t-ex",
            "backup.restore",
            {
                "phase": "execute",
                "backup_id": "ghost",
                "confirm_token": token,
                "attestation": True,
                "typed_confirm": "CONFIRM",
            },
        )
        assert not resp["ok"]  # backup missing -> backup-error or safety refusal


class TestPatchModem:
    def test_modem_modulus_swap(self, svc):
        new_modulus = bytes(range(256)).hex()
        plan, token = plan_and_token(
            svc,
            "service.patch_modem",
            {"name": "md1img", "new_modulus_hex": new_modulus, "phase": "plan"},
        )
        assert plan["risk"] == "yellow"
        resp = svc.handle_request(
            "t-ex",
            "service.patch_modem",
            {
                "phase": "execute",
                "name": "md1img",
                "new_modulus_hex": new_modulus,
                "confirm_token": token,
            },
        )
        assert resp["ok"], resp
        assert resp["result"]["verified"] is True
        assert resp["result"]["backup_id"]

    def test_patch_without_key_refused(self, svc):
        plan, token = plan_and_token(
            svc, "service.patch_modem", {"name": "md1img", "phase": "plan"}
        )
        resp = svc.handle_request(
            "t-ex",
            "service.patch_modem",
            {"phase": "execute", "name": "md1img", "confirm_token": token},
        )
        assert not resp["ok"]


class TestVbmeta:
    def test_vbmeta_patch(self, svc):
        plan, token = plan_and_token(svc, "service.vbmeta_patch", {"phase": "plan", "vbmode": 3})
        assert plan["risk"] == "yellow"
        resp = svc.handle_request(
            "t-ex",
            "service.vbmeta_patch",
            {"phase": "execute", "vbmode": 3, "confirm_token": token},
        )
        assert resp["ok"], resp
        assert resp["result"]["verified"] is True
        patched = svc.adapter.read_partition("vbmeta").data
        assert patched[0x78:0x7C] == (3).to_bytes(4, "big")


class TestUnlockLock:
    def test_unlock_bl_red(self, svc):
        plan, token = plan_and_token(svc, "service.unlock_bl", {"phase": "plan"})
        assert plan["risk"] == "red"
        resp = svc.handle_request(
            "t-ex",
            "service.unlock_bl",
            {
                "phase": "execute",
                "confirm_token": token,
                "attestation": True,
                "typed_confirm": "CONFIRM",
            },
        )
        assert resp["ok"], resp
        assert resp["result"]["seccfg"] == "unlock"

    def test_lock_bl(self, svc):
        _, token = plan_and_token(svc, "service.lock_bl", {"phase": "plan"})
        resp = svc.handle_request(
            "t-ex",
            "service.lock_bl",
            {
                "phase": "execute",
                "confirm_token": token,
                "attestation": True,
                "typed_confirm": "CONFIRM",
            },
        )
        assert resp["ok"], resp


class TestEraseFrp:
    def test_erase_frp(self, svc):
        _, token = plan_and_token(svc, "service.erase_frp", {"phase": "plan"})
        resp = svc.handle_request(
            "t-ex",
            "service.erase_frp",
            {"phase": "execute", "confirm_token": token},
        )
        assert resp["ok"], resp
        assert resp["result"]["verified"] is True


class TestImei:
    def test_imei_read_green(self, svc):
        resp = svc.handle_request("t-ir", "service.imei_read", {})
        assert resp["ok"], resp
        assert resp["result"]["imei1"] == "490154203237518"

    def test_imei_write_red(self, svc):
        plan, token = plan_and_token(
            svc,
            "service.imei_write",
            {"imei1": "490154203237518", "imei2": "356938035643809", "phase": "plan"},
        )
        assert plan["risk"] == "red"
        assert plan["requires_attestation"]
        resp = svc.handle_request(
            "t-ex",
            "service.imei_write",
            {
                "phase": "execute",
                "imei1": "490154203237518",
                "imei2": "356938035643809",
                "confirm_token": token,
                "attestation": True,
                "typed_confirm": "CONFIRM",
            },
        )
        assert resp["ok"], resp
        assert resp["result"]["verified"] is True


class TestSessionLedger:
    def test_mutations_are_logged(self, svc, tmp_path):
        _, token = plan_and_token(
            svc, "service.erase_frp", {"phase": "plan"}
        )
        svc.handle_request(
            "t-ex", "service.erase_frp", {"phase": "execute", "confirm_token": token}
        )
        import glob

        files = glob.glob(str(tmp_path / "sessions" / "**" / "*.jsonl"), recursive=True)
        assert files
        content = open(files[0]).read()
        assert "mutation" in content
        assert "service.erase_frp" in content


class TestTokenBinding:
    def test_token_not_transferable_between_params(self, svc):
        _, token = plan_and_token(
            svc, "partition.write", {"name": "nvdata", "data_hex": "00"}
        )
        resp = svc.handle_request(
            "t-ex",
            "partition.write",
            {
                "phase": "execute",
                "name": "frp",  # different target
                "data_hex": "00",
                "confirm_token": token,
            },
        )
        assert not resp["ok"]
        assert resp["error"]["code"] == "refused-by-safety"
