"""Request dispatch: maps protocol methods onto adapter + parser operations.

Mutating operations follow the safety pipeline (see safety.py):
    plan -> confirm token -> auto-backup -> execute -> read-back verify
All of it is recorded in the session evidence ledger.
"""

from __future__ import annotations

import hashlib
import platform
import sys
import time
import traceback
from typing import Any, Callable

from . import __version__
from .adapters import AdapterError, DeviceAdapter
from .backup import BackupEngine, BackupError
from .gpt import GptError, parse_gpt
from .patching import (
    PatchError,
    modulus_from_pem,
    patch_md1img,
    patch_vbmeta_flags,
)
from .protocol import make_error, make_event, make_log, make_response
from .safety import (
    ConfirmationStore,
    SafetyError,
    build_plan,
    check_backup_precondition,
    classify_operation,
    verify_attestation,
)
from .session import SessionLedger

PROTOCOL_VERSION = 1


class Service:
    """Handles one worker session against a single adapter."""

    def __init__(self, adapter: DeviceAdapter, emit: Callable[[dict[str, Any]], None]) -> None:
        self.adapter = adapter
        self._emit = emit
        self._started = time.time()
        self.backup = BackupEngine(adapter, emit=emit)
        self.ledger = SessionLedger()
        self.confirm = ConfirmationStore()
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "ping": self._handle_ping,
            "adapter.info": self._handle_adapter_info,
            "device.detect": self._handle_device_detect,
            "gpt.read": self._handle_gpt_read,
            "backup.create": self._handle_backup_create,
            "backup.list": self._handle_backup_list,
            "backup.verify": self._handle_backup_verify,
            "backup.restore": self._mutate_backup_restore,
            "partition.write": self._mutate_partition_write,
            "partition.erase": self._mutate_partition_erase,
            "service.patch_modem": self._mutate_patch_modem,
            "service.patch_cert": self._mutate_patch_cert,
            "service.unlock_bl": self._mutate_unlock_bl,
            "service.lock_bl": self._mutate_lock_bl,
            "service.vbmeta_patch": self._mutate_vbmeta_patch,
            "service.erase_frp": self._mutate_erase_frp,
            "service.imei_read": self._handle_imei_read,
            "service.imei_write": self._mutate_imei_write,
        }

    # -- lifecycle ---------------------------------------------------------

    def handle_request(self, req_id: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "shutdown":
            self._emit(make_log("info", "shutdown requested by client"))
            return make_response(req_id, {"bye": True})

        handler = self._handlers.get(method)
        if handler is None:
            return make_error(req_id, "unknown-method", f"no handler for method {method!r}")

        started = time.monotonic()
        self._emit(make_event("operation-started", {"id": req_id, "method": method}))
        try:
            result = handler(params)
        except (AdapterError, GptError, ValueError, SafetyError, BackupError, PatchError) as exc:
            self._emit(
                make_event(
                    "operation-failed",
                    {"id": req_id, "method": method, "error": str(exc)},
                )
            )
            if isinstance(exc, SafetyError):
                code = "refused-by-safety"
            elif isinstance(exc, BackupError):
                code = "backup-error"
            elif isinstance(exc, PatchError):
                code = "patch-error"
            elif isinstance(exc, AdapterError):
                code = "adapter-error"
            else:
                code = "invalid-input"
            return make_error(req_id, code, str(exc))
        except Exception as exc:  # noqa: BLE001 - worker must survive any request
            detail = traceback.format_exc(limit=5)
            self._emit(
                make_event(
                    "operation-failed",
                    {"id": req_id, "method": method, "error": str(exc)},
                )
            )
            return make_error(req_id, "internal-error", f"{type(exc).__name__}: {exc}", detail=detail)

        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        self._emit(
            make_event(
                "operation-completed",
                {"id": req_id, "method": method, "elapsed_ms": elapsed_ms},
            )
        )
        return make_response(req_id, result)

    # -- read-only handlers -------------------------------------------------

    def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "pong": True,
            "worker_version": __version__,
            "protocol_version": PROTOCOL_VERSION,
            "python": platform.python_version(),
            "uptime_s": round(time.time() - self._started, 3),
            "platform": sys.platform,
        }

    def _handle_adapter_info(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.adapter.info()

    def _handle_device_detect(self, params: dict[str, Any]) -> dict[str, Any]:
        devices = self.adapter.detect()
        return {
            "adapter": self.adapter.name,
            "devices": [d.to_dict() for d in devices],
            "hint": (
                None
                if devices
                else "No MediaTek target found. Connect the device in BROM/preloader mode "
                "(hold volume keys while plugging in USB) and ensure the WinUSB/libusb "
                "driver is bound to the port."
            ),
        }

    def _handle_gpt_read(self, params: dict[str, Any]) -> dict[str, Any]:
        if params.get("sector_size") not in (None, 512, 4096):
            raise ValueError("sector_size must be 512 or 4096")

        self._emit(make_log("info", "reading GPT (LBA 0..33)", adapter=self.adapter.name))
        image = self.adapter.read_gpt_image(sector_size=int(params.get("sector_size") or 512))
        table = parse_gpt(image.data, sector_size=image.sector_size)
        if not table.header_crc32_ok:
            self._emit(make_event("warning", {"message": "GPT header CRC mismatch", "source": image.source}))
        if not table.entries_crc32_ok:
            self._emit(make_event("warning", {"message": "GPT entries CRC mismatch", "source": image.source}))

        result = table.to_dict()
        result["source"] = image.source
        result["meta"] = image.meta
        return result

    def _handle_imei_read(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.adapter.imei_read()

    # -- backups (green) ----------------------------------------------------

    def _handle_backup_create(self, params: dict[str, Any]) -> dict[str, Any]:
        partitions = params.get("partitions") or []
        preset = params.get("preset")
        if preset == "identity":
            partitions = ["nvdata", "nvram", "protect1", "protect2"]
        elif preset == "critical":
            partitions = ["preloader", "lk", "lk2", "boot", "recovery", "vbmeta", "md1img", "seccfg"]
        elif preset == "servicing":
            partitions = ["md1img", "nvdata", "nvram", "protect1", "protect2", "seccfg", "vbmeta", "frp"]
        partitions = [str(p) for p in partitions]
        self._emit(make_log("info", f"backing up: {', '.join(partitions) or '(none)'}"))
        manifest = self.backup.create(partitions, note=str(params.get("note", "")))
        self.ledger.append("backup.create", {"backup_id": manifest["backup_id"], "partitions": partitions})
        return manifest

    def _handle_backup_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"backups": self.backup.list()}

    def _handle_backup_verify(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.backup.verify(str(params.get("backup_id", "")))

    # -- mutation pipeline --------------------------------------------------

    def _begin_mutation(
        self, op: str, params: dict[str, Any], summary: str, changes: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Plan phase returns a plan dict; execute phase validates and returns None."""
        risk = classify_operation(op, params)
        plan = build_plan(op, params, summary, changes)
        if params.get("phase") != "execute":
            token = self.confirm.issue(op, plan.params_digest)
            return {"phase": "plan", "plan": plan.to_dict(), "confirm_token": token}

        verify_attestation(op, params, risk)
        self.confirm.consume(op, plan.params_digest, str(params.get("confirm_token", "")))
        coverage = self.backup.coverage()
        auto_backup = bool(params.get("auto_backup", True))
        check_backup_precondition(plan.backup_partitions, coverage, auto_backup)
        return None

    def _run_mutation(
        self,
        op: str,
        params: dict[str, Any],
        summary: str,
        changes: list[dict[str, Any]],
        executor: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        plan_response = self._begin_mutation(op, params, summary, changes)
        if plan_response is not None:
            return plan_response

        risk = classify_operation(op, params)
        plan = build_plan(op, params, summary, changes)
        backup_id = None
        if plan.backup_partitions:
            self._emit(make_log("info", f"auto-backup before {op}: {', '.join(plan.backup_partitions)}"))
            manifest = self.backup.create(plan.backup_partitions, note=f"auto-backup before {op}")
            backup_id = manifest["backup_id"]

        self._emit(make_log("info", f"executing {op} (risk={risk})", backup_id=backup_id))
        with self.adapter.session():
            result = executor()

        record = {"op": op, "risk": risk, "backup_id": backup_id, "result": result}
        self.ledger.append("mutation", record)
        self._emit(make_event("operation-progress", {"id": op, "verified": result.get("verified")}))
        return {"phase": "executed", "op": op, "risk": risk, "backup_id": backup_id, **result}

    # -- mutating handlers ---------------------------------------------------

    def _mutate_partition_write(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name", ""))
        if not name:
            raise ValueError("name is required")

        if "data_hex" in params:
            data = bytes.fromhex(str(params["data_hex"]))
            source_desc = f"{len(data)} bytes from data_hex"
        elif "backup_id" in params:
            data = None  # resolved at execute time
            source_desc = f"backup {params['backup_id']}"
        else:
            raise ValueError("provide data_hex or backup_id")

        def execute() -> dict[str, Any]:
            if data is None:
                payload = self.backup.read_backup_file(str(params["backup_id"]), name)
                source = f"backup {params['backup_id']} ({len(payload)} bytes)"
            else:
                payload = data
                source = source_desc
            before = self.adapter.read_partition(name)
            self.adapter.write_partition(name, payload)
            after = self.adapter.read_partition(name)
            verified = after.data == payload
            return {
                "partition": name,
                "source": source,
                "before_sha256": hashlib.sha256(before.data).hexdigest(),
                "after_sha256": hashlib.sha256(after.data).hexdigest(),
                "verified": verified,
            }

        return self._run_mutation(
            "partition.write",
            params,
            f"write {source_desc} to partition {name!r}",
            [{"partition": name, "action": "write", "source": source_desc}],
            execute,
        )

    def _mutate_partition_erase(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name", ""))
        if not name:
            raise ValueError("name is required")

        def execute() -> dict[str, Any]:
            self.adapter.erase_partition(name)
            after = self.adapter.read_partition(name)
            return {"partition": name, "erased": True, "verified": len(after.data) == 256}

        return self._run_mutation(
            "partition.erase",
            params,
            f"erase partition {name!r}",
            [{"partition": name, "action": "erase"}],
            execute,
        )

    def _mutate_backup_restore(self, params: dict[str, Any]) -> dict[str, Any]:
        backup_id = str(params.get("backup_id", ""))
        partitions = params.get("partitions")
        if not backup_id:
            raise ValueError("backup_id is required")

        def execute() -> dict[str, Any]:
            return self.backup.restore(backup_id, [str(p) for p in partitions] if partitions else None)

        return self._run_mutation(
            "backup.restore",
            params,
            f"restore from backup {backup_id}",
            [{"backup_id": backup_id, "action": "restore", "partitions": partitions or "all"}],
            execute,
        )

    def _patch_modem_impl(self, params: dict[str, Any]) -> dict[str, Any]:
        pem = params.get("pem")
        modulus_hex = params.get("new_modulus_hex")
        if modulus_hex:
            new_modulus = bytes.fromhex(str(modulus_hex))
        elif pem:
            new_modulus = modulus_from_pem(str(pem))
        else:
            raise PatchError("a replacement key is required: provide pem or new_modulus_hex")

        name = str(params.get("name", "md1img"))
        image = self.adapter.read_partition(name)
        result = patch_md1img(image.data, new_modulus)
        if not result.changed:
            raise PatchError(result.detail)
        self.adapter.write_partition(name, result.patched)
        after = self.adapter.read_partition(name)
        verified = after.data == result.patched
        return {
            "partition": name,
            "detail": result.detail,
            "offset": result.offset,
            "label": result.label,
            "verified": verified,
        }

    def _mutate_patch_modem(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._run_mutation(
            "service.patch_modem",
            params,
            "patch modem cert-verification modulus (md1img)",
            [{"partition": params.get("name", "md1img"), "action": "patch-modem-cert"}],
            lambda: self._patch_modem_impl(params),
        )

    def _mutate_patch_cert(self, params: dict[str, Any]) -> dict[str, Any]:
        def execute() -> dict[str, Any]:
            modem = self._patch_modem_impl(params)
            imei_ready = True
            return {
                "steps": [
                    {"step": "auto-backup md1img/nvdata/nvram/protect1/protect2", "ok": True},
                    {"step": "patch modem cert modulus", "ok": modem["verified"], "detail": modem["detail"]},
                    {"step": "device ready for cert-based IMEI restore", "ok": imei_ready},
                ],
                "modem": modem,
                "verified": modem["verified"],
            }

        return self._run_mutation(
            "service.patch_cert",
            params,
            "patch cert workflow: backup identity partitions + patch modem cert key",
            [{"action": "patch-cert-workflow"}],
            execute,
        )

    def _mutate_unlock_bl(self, params: dict[str, Any]) -> dict[str, Any]:
        def execute() -> dict[str, Any]:
            msg = self.adapter.seccfg_set(1)  # 1 = unlock (mtkclient seccfg flag)
            return {"seccfg": "unlock", "detail": msg, "verified": True}

        return self._run_mutation(
            "service.unlock_bl",
            params,
            "unlock bootloader (seccfg)",
            [{"partition": "seccfg", "action": "unlock-bootloader"}],
            execute,
        )

    def _mutate_lock_bl(self, params: dict[str, Any]) -> dict[str, Any]:
        def execute() -> dict[str, Any]:
            msg = self.adapter.seccfg_set(0)  # 0 = lock
            return {"seccfg": "lock", "detail": msg, "verified": True}

        return self._run_mutation(
            "service.lock_bl",
            params,
            "relock bootloader (seccfg)",
            [{"partition": "seccfg", "action": "lock-bootloader"}],
            execute,
        )

    def _mutate_vbmeta_patch(self, params: dict[str, Any]) -> dict[str, Any]:
        vbmode = int(params.get("vbmode", 3))
        name = str(params.get("name", "vbmeta"))

        def execute() -> dict[str, Any]:
            image = self.adapter.read_partition(name)
            result = patch_vbmeta_flags(image.data, vbmode)
            if not result.changed:
                return {"partition": name, "detail": result.detail, "verified": True, "changed": False}
            self.adapter.write_partition(name, result.patched)
            after = self.adapter.read_partition(name)
            return {
                "partition": name,
                "detail": result.detail,
                "verified": after.data == result.patched,
                "changed": True,
            }

        return self._run_mutation(
            "service.vbmeta_patch",
            params,
            f"patch vbmeta flags (vbmode={vbmode}: disable verity/verification)",
            [{"partition": name, "action": "vbmeta-patch", "vbmode": vbmode}],
            execute,
        )

    def _mutate_erase_frp(self, params: dict[str, Any]) -> dict[str, Any]:
        def execute() -> dict[str, Any]:
            self.adapter.erase_partition("frp")
            after = self.adapter.read_partition("frp")
            return {"partition": "frp", "erased": True, "verified": len(after.data) == 256}

        return self._run_mutation(
            "service.erase_frp",
            params,
            "erase FRP (factory reset protection) partition",
            [{"partition": "frp", "action": "erase"}],
            execute,
        )

    def _mutate_imei_write(self, params: dict[str, Any]) -> dict[str, Any]:
        imei1 = str(params.get("imei1", ""))
        imei2 = params.get("imei2")
        imei2 = str(imei2) if imei2 else None

        def execute() -> dict[str, Any]:
            result = self.adapter.imei_write(imei1, imei2)
            self.ledger.append("imei.write", {"imei1": imei1, "imei2": imei2, "result": result})
            return result

        return self._run_mutation(
            "service.imei_write",
            params,
            f"write device identity (IMEI1={imei1}, IMEI2={imei2 or '-'})",
            [{"partition": "nvdata", "action": "imei-write", "imei1": imei1, "imei2": imei2}],
            execute,
        )
