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

  async request(method: string): Promise<Record<string, unknown>> {
    const id = `mock-${++this.seq}`;
    this.emit({ v: 1, type: "event", event: "operation-started", data: { id, method } });
    await new Promise((r) => setTimeout(r, 180 + Math.random() * 320));

    let result: Record<string, unknown>;
    switch (method) {
      case "ping":
        result = {
          pong: true,
          worker_version: "0.1.0 (browser mock)",
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
          read_only: true,
          description: "Deterministic fixture transport embedded in the UI bundle.",
        };
        break;
      case "device.detect":
        result = fixtureDetect() as unknown as Record<string, unknown>;
        break;
      case "gpt.read":
        result = fixtureGpt() as unknown as Record<string, unknown>;
        break;
      case "shutdown":
        result = { bye: true };
        break;
      default:
        throw new Error(`unknown method: ${method}`);
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
