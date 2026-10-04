"""Operation safety engine: risk classes, plans, confirmation tokens.

Every mutating operation flows through:

    plan  -> risk class + exact changes + preconditions + confirm token
    execute -> token check + backup enforcement + read-back verification

Risk classes follow SAFETY_POLICY.md:
    green  - read-only / backup creation
    yellow - controlled modification (auto-backup required)
    red    - boot-critical or identity operations (attestation + typed confirm)
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

RISK_GREEN = "green"
RISK_YELLOW = "yellow"
RISK_RED = "red"

# Operation registry: op name -> (risk, backup partitions, needs attestation)
# Backup partitions may contain "{name}" placeholders filled from params.
OP_REGISTRY: dict[str, dict[str, Any]] = {
    "backup.create": {"risk": RISK_GREEN, "backup": [], "attestation": False},
    "backup.verify": {"risk": RISK_GREEN, "backup": [], "attestation": False},
    "backup.list": {"risk": RISK_GREEN, "backup": [], "attestation": False},
    "backup.restore": {"risk": RISK_RED, "backup": [], "attestation": True},
    "ping": {"risk": RISK_GREEN, "backup": [], "attestation": False},
    "adapter.info": {"risk": RISK_GREEN, "backup": [], "attestation": False},
    "device.detect": {"risk": RISK_GREEN, "backup": [], "attestation": False},
    "gpt.read": {"risk": RISK_GREEN, "backup": [], "attestation": False},
    "service.imei_read": {"risk": RISK_GREEN, "backup": [], "attestation": False},
    "partition.write": {"risk": RISK_YELLOW, "backup": ["{name}"], "attestation": False},
    "partition.erase": {"risk": RISK_RED, "backup": ["{name}"], "attestation": True},
    "service.patch_modem": {"risk": RISK_YELLOW, "backup": ["md1img"], "attestation": False},
    "service.patch_cert": {
        "risk": RISK_YELLOW,
        "backup": ["md1img", "nvdata", "nvram", "protect1", "protect2"],
        "attestation": False,
    },
    "service.unlock_bl": {"risk": RISK_RED, "backup": ["seccfg"], "attestation": True},
    "service.lock_bl": {"risk": RISK_RED, "backup": ["seccfg"], "attestation": True},
    "service.vbmeta_patch": {"risk": RISK_YELLOW, "backup": ["vbmeta"], "attestation": False},
    "service.erase_frp": {"risk": RISK_YELLOW, "backup": ["frp"], "attestation": False},
    "service.imei_write": {
        "risk": RISK_RED,
        "backup": ["nvdata", "nvram", "protect1", "protect2"],
        "attestation": True,
    },
}

# Partitions whose corruption bricks the device (SAFETY_POLICY red zone).
BOOT_CRITICAL = {
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
    "md1img_a",
    "md1img_b",
    "seccfg",
    "nvcfg",
}


class SafetyError(RuntimeError):
    """Raised when an operation is refused by the safety engine."""


@dataclass
class OperationPlan:
    op: str
    risk: str
    summary: str
    changes: list[dict[str, Any]]
    backup_partitions: list[str]
    preconditions: list[dict[str, Any]]
    requires_attestation: bool
    params_digest: str
    created: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "risk": self.risk,
            "summary": self.summary,
            "changes": self.changes,
            "backup_partitions": self.backup_partitions,
            "preconditions": self.preconditions,
            "requires_attestation": self.requires_attestation,
            "params_digest": self.params_digest,
            "created": self.created,
        }


def _params_digest(op: str, params: dict[str, Any]) -> str:
    """Digest of the operation-defining parameters (excludes phase/token/etc.)."""
    core = {
        k: v
        for k, v in params.items()
        if k not in ("phase", "confirm_token", "auto_backup", "attestation", "typed_confirm")
    }
    blob = json.dumps({"op": op, "params": core}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def make_token(op: str, params_digest: str, nonce: str) -> str:
    """Confirmation token bound to the exact operation parameters."""
    return hashlib.sha256(f"{op}:{params_digest}:{nonce}".encode()).hexdigest()[:32]


class ConfirmationStore:
    """Worker-side store binding plan tokens to operation parameters.

    The UI receives only the token; the nonce stays in the worker so a token
    cannot be regenerated outside a plan issued by this session. Tokens are
    consumed on successful execution (one-shot).
    """

    def __init__(self) -> None:
        self._nonces: dict[str, str] = {}

    def issue(self, op: str, params_digest: str) -> str:
        nonce = secrets.token_hex(8)
        token = make_token(op, params_digest, nonce)
        self._nonces[f"{op}:{params_digest}"] = nonce
        return token

    def consume(self, op: str, params_digest: str, token: str) -> None:
        key = f"{op}:{params_digest}"
        nonce = self._nonces.get(key)
        if nonce is None:
            raise SafetyError("no confirmation token was issued for this operation plan")
        expected = make_token(op, params_digest, nonce)
        if not secrets.compare_digest(expected, token):
            raise SafetyError(
                "confirmation token does not match this operation plan "
                "(parameters changed since planning, or token is invalid)"
            )
        del self._nonces[key]


def classify_operation(op: str, params: dict[str, Any]) -> str:
    """Effective risk class (registry + boot-critical target escalation)."""
    entry = OP_REGISTRY.get(op)
    if entry is None:
        raise SafetyError(f"unknown operation: {op}")
    risk = entry["risk"]
    # Boot-critical escalation applies to generic partition ops (the operator
    # picks the target). Curated service ops keep their registry risk class.
    if op in ("partition.write", "partition.erase"):
        name = str(params.get("name", "")).lower()
        base = name[:-2] if name.endswith(("_a", "_b")) else name
        if name in BOOT_CRITICAL or base in BOOT_CRITICAL:
            risk = RISK_RED
    return risk


def build_plan(
    op: str,
    params: dict[str, Any],
    summary: str,
    changes: list[dict[str, Any]],
    preconditions: list[dict[str, Any]] | None = None,
) -> OperationPlan:
    """Build an operation plan (token issuance is separate via ConfirmationStore)."""
    entry = OP_REGISTRY.get(op)
    if entry is None:
        raise SafetyError(f"unknown operation: {op}")

    backup_parts = [p.format(**params) for p in entry["backup"]]
    risk = classify_operation(op, params)

    return OperationPlan(
        op=op,
        risk=risk,
        summary=summary,
        changes=changes,
        backup_partitions=backup_parts,
        preconditions=preconditions or [],
        requires_attestation=entry["attestation"] or risk == RISK_RED,
        params_digest=_params_digest(op, params),
    )


def verify_attestation(op: str, params: dict[str, Any], risk: str) -> None:
    """Enforce attestation + typed confirmation for red-class operations."""
    entry = OP_REGISTRY[op]
    if not (entry["attestation"] or risk == RISK_RED):
        return
    if params.get("attestation") is not True:
        raise SafetyError(
            "this operation requires an explicit legal/safety attestation "
            '(params["attestation"] = true)'
        )
    typed = params.get("typed_confirm", "")
    if str(typed) != "CONFIRM":
        raise SafetyError('red-class operations require typed_confirm = "CONFIRM"')


def check_backup_precondition(
    required: list[str],
    coverage: dict[str, str],
    auto_backup: bool,
) -> None:
    """Refuse execution when affected partitions have no verified backup.

    ``coverage`` maps partition name -> backup id covering it. When
    ``auto_backup`` is true the executor performs the backup first; this
    check only rejects the *plan* of executing without any backup path.
    """
    missing = [p for p in required if p not in coverage]
    if missing and not auto_backup:
        raise SafetyError(
            "no verified backup covers: "
            + ", ".join(missing)
            + " (create a backup or pass auto_backup=true)"
        )
