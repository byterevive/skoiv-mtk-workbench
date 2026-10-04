/** Transport layer: Tauri IPC when running in the desktop shell, an in-page
 *  mock otherwise so the UI is fully explorable in a plain browser preview. */

import type { WorkerEventMsg } from "./types";
import { fixtureDetect, fixtureGpt } from "./fixtures";

export interface Transport {
  readonly mode: "tauri" | "mock";
  request(method: string, params?: Record<string, unknown>): Promise<Record<string, unknown>>;
  onEvent(cb: (msg: WorkerEventMsg) => void): () => void;
}

function isTauri(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

class TauriTransport implements Transport {
  readonly mode = "tauri" as const;

  async request(method: string, params: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
    const { invoke } = await import("@tauri-apps/api/core");
    return (await invoke("worker_request", { method, params })) as Record<string, unknown>;
  }

  onEvent(cb: (msg: WorkerEventMsg) => void): () => void {
    let unlisten: (() => void) | null = null;
    let cancelled = false;
    import("@tauri-apps/api/event").then(({ listen }) => {
      listen<WorkerEventMsg>("worker-event", (e) => cb(e.payload)).then((fn) => {
        if (cancelled) fn();
        else unlisten = fn;
      });
    });
    return () => {
      cancelled = true;
      if (unlisten) unlisten();
    };
  }
}

class MockTransport implements Transport {
  readonly mode = "mock" as const;
  private listeners = new Set<(msg: WorkerEventMsg) => void>();
  private seq = 0;
  private tokens = new Map<string, string>(); // op:paramsDigest -> token
  private store = new Map<string, Uint8Array>(); // partition -> content
  private backups = new Map<string, Record<string, unknown>>();
  private backupSeq = 0;

  constructor() {
    setTimeout(() => {
      this.emit({
        v: 1,
        type: "event",
        event: "worker-health",
        data: { status: "ready", adapter: "browser-mock" },
      });
      this.emit({
        v: 1,
        type: "event",
        event: "log",
        data: { level: "info", message: "browser mock transport started (no hardware access)" },
      });
    }, 150);
  }

  private emit(msg: WorkerEventMsg) {
    for (const cb of this.listeners) cb(msg);
  }

  onEvent(cb: (msg: WorkerEventMsg) => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  // -- tiny deterministic digest (mock-only param binding) -----------------
  private digest(op: string, params: Record<string, unknown>): string {
    const core = Object.fromEntries(
      Object.entries(params).filter(
        ([k]) => !["phase", "confirm_token", "auto_backup", "attestation", "typed_confirm"].includes(k),
      ),
    );
    const blob = JSON.stringify({ op, params: core }, Object.keys({ op: 0, ...core }).sort());
    let h1 = 0x811c9dc5;
    for (let i = 0; i < blob.length; i++) {
      h1 ^= blob.charCodeAt(i);
      h1 = Math.imul(h1, 0x01000193) >>> 0;
    }
    return h1.toString(16).padStart(8, "0") + blob.length.toString(16);
  }

  private partitionContent(name: string): Uint8Array {
    const key = name.toLowerCase();
    if (!this.store.has(key)) {
      const buf = new Uint8Array(256);
      for (let i = 0; i < buf.length; i++) buf[i] = (key.charCodeAt(i % key.length) + i) & 0xff;
      this.store.set(key, buf);
    }
    return this.store.get(key)!;
  }

  private shaish(data: Uint8Array): string {
    // Labelled as non-cryptographic in the UI (mock mode banner).
    let h = 0x811c9dc5;
    for (let i = 0; i < data.length; i++) {
      h ^= data[i];
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return `mock-${h.toString(16).padStart(8, "0")}-${data.length}`;
  }

  private beginMutation(op: string, params: Record<string, unknown>): Record<string, unknown> {
    const risk =
      op.startsWith("service.unlock") ||
      op.startsWith("service.lock") ||
      op === "service.imei_write" ||
      op === "partition.erase" ||
      op === "backup.restore"
        ? "red"
        : "yellow";
    const backupPartitions: Record<string, string[]> = {
      "service.patch_modem": ["md1img"],
      "service.patch_cert": ["md1img", "nvdata", "nvram", "protect1", "protect2"],
      "service.vbmeta_patch": ["vbmeta"],
      "service.erase_frp": ["frp"],
      "service.unlock_bl": ["seccfg"],
      "service.lock_bl": ["seccfg"],
      "service.imei_write": ["nvdata", "nvram", "protect1", "protect2"],
      "partition.erase": [String(params.name ?? "")],
      "partition.write": [String(params.name ?? "")],
      "backup.restore": [],
    };
    const plan = {
      op,
      risk,
      summary: `${op} (browser mock plan)`,
      changes: [{ action: op.split(".")[1] ?? op, ...params }],
      backup_partitions: backupPartitions[op] ?? [],
      preconditions: [],
      requires_attestation: risk === "red",
      params_digest: this.digest(op, params),
      created: Date.now() / 1000,
    };
    const token = `mock-${(this.tokens.size + 1).toString(16).padStart(6, "0")}`;
    this.tokens.set(`${op}:${plan.params_digest}`, token);
    return { phase: "plan", plan, confirm_token: token };
  }

  private runMutation(op: string, params: Record<string, unknown>): Record<string, unknown> {
    const plan = this.beginMutation(op, params) as { plan: Record<string, unknown>; confirm_token: string };
    const digest = String(plan.plan.params_digest);
    const key = `${op}:${digest}`;
    const stored = this.tokens.get(key);
    if (params.phase !== "execute") return plan;
    if (!stored || stored !== params.confirm_token) {
      throw new Error("confirmation token does not match this operation plan (refused by safety)");
    }
    if (plan.plan.risk === "red" || plan.plan.requires_attestation) {
      if (params.attestation !== true || params.typed_confirm !== "CONFIRM") {
        throw new Error('red-class operations require attestation:true and typed_confirm:"CONFIRM" (refused by safety)');
      }
    }
    this.tokens.delete(key);

    const backupParts = plan.plan.backup_partitions as string[];
    let backupId: string | null = null;
    if (backupParts.length > 0 && params.auto_backup !== false) {
      backupId = this.createBackup(backupParts, `auto-backup before ${op}`) as string;
    }

    let verified = true;
    let detail: Record<string, unknown> = {};
    if (op === "partition.write" || op === "service.patch_modem" || op === "service.patch_cert") {
      const name = String(params.name ?? (op === "partition.write" ? "" : "md1img"));
      const buf = this.partitionContent(name);
      // Deterministic mock "patch": flip a byte so read-back differs visibly.
      buf[0] = (buf[0] + 1) & 0xff;
      detail = { partition: name, detail: "mock patch applied (fixture content mutated)" };
    } else if (op === "partition.erase" || op === "service.erase_frp") {
      const name = String(params.name ?? "frp");
      this.store.set(name.toLowerCase(), new Uint8Array(256));
      detail = { partition: name, erased: true };
    } else if (op === "service.vbmeta_patch") {
      const buf = this.partitionContent("vbmeta");
      buf[0x78] = 3;
      detail = { partition: "vbmeta", detail: "mock vbmeta flags set to 3" };
    } else if (op === "service.unlock_bl" || op === "service.lock_bl") {
      detail = { seccfg: op.includes("unlock") ? "unlock" : "lock" };
    } else if (op === "service.imei_write") {
      detail = { written: { imei1: params.imei1, imei2: params.imei2 } };
    } else if (op === "backup.restore") {
      detail = { backup_id: params.backup_id, restored: true };
    }
    return { phase: "executed", op, risk: plan.plan.risk, backup_id: backupId, verified, ...detail };
  }

  private createBackup(partitions: string[], note: string): string {
    const id = `mock-backup-${++this.backupSeq}`;
    const parts: Record<string, { file: string; size: number; sha256: string }> = {};
    for (const p of partitions) {
      const content = this.partitionContent(p);
      parts[p.toLowerCase()] = { file: `${p}.bin`, size: content.length, sha256: this.shaish(content) };
    }
    this.backups.set(id, {
      backup_id: id,
      created: Date.now() / 1000,
      adapter: "browser-mock",
      source: "mock:fixture",
      note,
      partitions: parts,
    });
    return id;
  }

  async request(method: string, params: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
    const id = `mock-${++this.seq}`;
    this.emit({ v: 1, type: "event", event: "operation-started", data: { id, method } });
    await new Promise((r) => setTimeout(r, 180 + Math.random() * 320));

    let result: Record<string, unknown>;
    try {
      switch (method) {
        case "ping":
          result = {
            pong: true,
            worker_version: "0.2.0 (browser mock)",
            protocol_version: 1,
            python: "n/a",
            uptime_s: 0,
            platform: "browser",
          };
          break;
        case "adapter.info":
          result = {
            name: "browser-mock",
            mode: "fixture",
            read_only: false,
            description: "Deterministic fixture transport embedded in the UI bundle (simulated device state).",
          };
          break;
        case "device.detect":
          result = fixtureDetect() as unknown as Record<string, unknown>;
          break;
        case "gpt.read":
          result = fixtureGpt() as unknown as Record<string, unknown>;
          break;
        case "backup.create": {
          const preset = String(params.preset ?? "");
          const presetMap: Record<string, string[]> = {
            identity: ["nvdata", "nvram", "protect1", "protect2"],
            critical: ["preloader", "lk", "lk2", "boot", "recovery", "vbmeta", "md1img", "seccfg"],
            servicing: ["md1img", "nvdata", "nvram", "protect1", "protect2", "seccfg", "vbmeta", "frp"],
          };
          const parts = (presetMap[preset] ?? (params.partitions as string[]) ?? []) as string[];
          const backupId = this.createBackup(parts, String(params.note ?? ""));
          result = this.backups.get(backupId)!;
          break;
        }
        case "backup.list":
          result = { backups: [...this.backups.values()] };
          break;
        case "backup.verify":
          result = {
            backup_id: params.backup_id,
            ok: this.backups.has(String(params.backup_id)),
            partitions: {},
          };
          break;
        case "backup.restore":
          result = this.runMutation("backup.restore", params);
          break;
        case "service.imei_read":
          result = {
            imei1: "490154203237518",
            imei2: "356938035643809",
            all_imeis: ["490154203237518", "356938035643809"],
            source: "mock:fixture",
            luhn_valid: [true, true],
            note: "fixture IMEIs (standard Luhn-valid test values)",
          };
          break;
        case "service.patch_modem":
        case "service.patch_cert":
        case "service.unlock_bl":
        case "service.lock_bl":
        case "service.vbmeta_patch":
        case "service.erase_frp":
        case "service.imei_write":
        case "partition.write":
        case "partition.erase":
          result = this.runMutation(method, params);
          break;
        case "shutdown":
          result = { bye: true };
          break;
        default:
          throw new Error(`unknown method: ${method}`);
      }
    } catch (err) {
      this.emit({
        v: 1,
        type: "event",
        event: "operation-failed",
        data: { id, method, error: String(err) },
      });
      throw err;
    }

    this.emit({
      v: 1,
      type: "event",
      event: "log",
      data: { level: "info", message: `${method} completed (mock)`, elapsed_ms: 240 },
    });
    this.emit({ v: 1, type: "event", event: "operation-completed", data: { id, method } });
    return result;
  }
}

export function getTransportMode(): "tauri" | "mock" {
  return isTauri() ? "tauri" : "mock";
}

export function createTransport(): Transport {
  return isTauri() ? new TauriTransport() : new MockTransport();
}
