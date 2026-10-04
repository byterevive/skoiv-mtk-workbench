"""Tests for the safety engine: risk classes, tokens, attestation, backups."""

from __future__ import annotations

import pytest

from skoiv_worker.safety import (
    RISK_GREEN,
    RISK_RED,
    RISK_YELLOW,
    ConfirmationStore,
    SafetyError,
    build_plan,
    check_backup_precondition,
    classify_operation,
    verify_attestation,
)


class TestRiskClassification:
    def test_reads_are_green(self):
        assert classify_operation("gpt.read", {}) == RISK_GREEN

    def test_known_risks(self):
        assert classify_operation("partition.write", {"name": "foo"}) == RISK_YELLOW
        assert classify_operation("partition.erase", {"name": "frp"}) == RISK_RED  # erase is destructive
        assert classify_operation("service.erase_frp", {}) == RISK_YELLOW
        assert classify_operation("service.unlock_bl", {}) == RISK_RED
        assert classify_operation("service.imei_write", {}) == RISK_RED

    def test_boot_critical_escalates_to_red(self):
        for name in ("boot", "lk", "preloader", "vbmeta", "seccfg", "recovery", "boot_a", "vbmeta_b"):
            assert classify_operation("partition.write", {"name": name}) == RISK_RED
            assert classify_operation("partition.erase", {"name": name}) == RISK_RED

    def test_unknown_op_raises(self):
        with pytest.raises(SafetyError):
            classify_operation("nope.nothing", {})


class TestConfirmation:
    def test_happy_path(self):
        store = ConfirmationStore()
        token = store.issue("partition.write", "abc123")
        store.consume("partition.write", "abc123", token)

    def test_wrong_token_rejected(self):
        store = ConfirmationStore()
        store.issue("partition.write", "abc123")
        with pytest.raises(SafetyError):
            store.consume("partition.write", "abc123", "f" * 32)

    def test_unissued_rejected(self):
        store = ConfirmationStore()
        with pytest.raises(SafetyError):
            store.consume("partition.write", "abc123", "f" * 32)

    def test_one_shot(self):
        store = ConfirmationStore()
        token = store.issue("partition.write", "abc123")
        store.consume("partition.write", "abc123", token)
        with pytest.raises(SafetyError):
            store.consume("partition.write", "abc123", token)

    def test_params_change_invalidates(self):
        store = ConfirmationStore()
        token = store.issue("partition.write", "abc123")
        with pytest.raises(SafetyError):
            store.consume("partition.write", "different", token)


class TestAttestation:
    def test_red_requires_attestation(self):
        with pytest.raises(SafetyError, match="attestation"):
            verify_attestation("service.unlock_bl", {}, RISK_RED)

    def test_red_requires_typed_confirm(self):
        with pytest.raises(SafetyError, match="CONFIRM"):
            verify_attestation(
                "service.unlock_bl", {"attestation": True, "typed_confirm": "confirm"}, RISK_RED
            )

    def test_red_passes_with_both(self):
        verify_attestation(
            "service.unlock_bl", {"attestation": True, "typed_confirm": "CONFIRM"}, RISK_RED
        )

    def test_yellow_needs_nothing(self):
        verify_attestation("partition.write", {}, RISK_YELLOW)


class TestBackupPrecondition:
    def test_existing_backup_ok(self):
        check_backup_precondition(["nvdata"], {"nvdata": "backup-1"}, auto_backup=False)

    def test_auto_backup_ok(self):
        check_backup_precondition(["nvdata"], {}, auto_backup=True)

    def test_missing_backup_refused(self):
        with pytest.raises(SafetyError, match="backup"):
            check_backup_precondition(["nvdata"], {}, auto_backup=False)

    def test_partial_coverage_refused(self):
        with pytest.raises(SafetyError):
            check_backup_precondition(["nvdata", "nvram"], {"nvdata": "b1"}, auto_backup=False)


class TestBuildPlan:
    def test_plan_shape(self):
        plan = build_plan(
            "partition.write",
            {"name": "boot", "data_hex": "00"},
            "write boot",
            [{"partition": "boot"}],
        )
        assert plan.op == "partition.write"
        assert plan.risk == RISK_RED  # boot is boot-critical
        assert plan.backup_partitions == ["boot"]
        assert plan.requires_attestation
        assert plan.params_digest

    def test_unknown_op(self):
        with pytest.raises(SafetyError):
            build_plan("nope", {}, "x", [])
