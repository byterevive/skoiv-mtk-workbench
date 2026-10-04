import { useEffect, useRef, useState } from "react";
import StatusBar from "./components/StatusBar";
import DevicePanel from "./components/DevicePanel";
import GptPanel from "./components/GptPanel";
import LogPanel from "./components/LogPanel";
import ServicePanel from "./components/ServicePanel";
import BackupPanel from "./components/BackupPanel";
import { createTransport, getTransportMode, type Transport } from "./transport";
import type {
  AdapterInfo,
  DetectResult,
  GptResult,
  LogEntry,
  PingResult,
  WorkerEventMsg,
} from "./types";

type WorkerStatus = "starting" | "ready" | "error" | "stopped";

export default function App() {
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus>("starting");
  const [adapterName, setAdapterName] = useState("");
  const [workerVersion, setWorkerVersion] = useState("");
  const [detect, setDetect] = useState<DetectResult | null>(null);
  const [gpt, setGpt] = useState<GptResult | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"gpt" | "service" | "backups">("gpt");
  const transportRef = useRef<Transport | null>(null);
  const logSeq = useRef(0);

  const pushLog = (level: string, message: string, ts = Date.now() / 1000) => {
    setLogs((prev) =>
      [{ id: ++logSeq.current, ts, level, message }, ...prev].slice(0, 400),
    );
  };

  useEffect(() => {
    const transport = createTransport();
    transportRef.current = transport;

    const unlisten = transport.onEvent((msg: WorkerEventMsg) => {
      if (msg.event === "worker-health") {
        const status = String(msg.data.status ?? "");
        if (status === "ready") setWorkerStatus("ready");
        else if (status === "error") setWorkerStatus("error");
        else if (status === "exited" || status === "stopped") setWorkerStatus("stopped");
        if (msg.data.message) pushLog("warn", `worker: ${msg.data.message}`);
        return;
      }
      if (msg.event === "log") {
        pushLog(String(msg.data.level ?? "info"), String(msg.data.message ?? ""));
        return;
      }
      if (msg.event === "warning") {
        pushLog("warn", String(msg.data.message ?? JSON.stringify(msg.data)));
        return;
      }
      if (msg.event === "operation-failed") {
        pushLog("error", `${msg.data.method ?? "operation"}: ${msg.data.error ?? "failed"}`);
      }
    });

    transport
      .request("ping")
      .then((r) => {
        const ping = r as unknown as PingResult;
        setWorkerVersion(ping.worker_version ?? "");
        setWorkerStatus("ready");
        pushLog("info", `worker ready (protocol v${ping.protocol_version})`);
        return transport.request("adapter.info");
      })
      .then((r) => {
        const info = r as unknown as AdapterInfo;
        setAdapterName(info.name);
        pushLog("info", `adapter: ${info.name} — ${info.description}`);
      })
      .catch((err: unknown) => {
        setWorkerStatus("error");
        pushLog("error", `worker unavailable: ${String(err)}`);
      });

    return unlisten;
  }, []);

  const run = async (label: string, fn: () => Promise<void>) => {
    if (!transportRef.current) return;
    setBusy(true);
    try {
      await fn();
    } catch (err: unknown) {
      pushLog("error", `${label}: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  };

  const onDetect = () =>
    run("device.detect", async () => {
      const r = await transportRef.current!.request("device.detect");
      setDetect(r as unknown as DetectResult);
    });

  const onReadGpt = () =>
    run("gpt.read", async () => {
      const r = await transportRef.current!.request("gpt.read");
      setGpt(r as unknown as GptResult);
    });

  return (
    <div className="app">
      <StatusBar
        workerStatus={workerStatus}
        transportMode={getTransportMode()}
        adapterName={adapterName}
        workerVersion={workerVersion}
      />

      <main className="layout">
        <div className="col">
          <DevicePanel detect={detect} busy={busy} onDetect={onDetect} />
          <div className="panel">
            <div className="panel-head">
              <h2>Workbench</h2>
              <div style={{ display: "flex", gap: 6 }}>
                <button className={`btn ${tab === "gpt" ? "" : "secondary"}`} onClick={() => setTab("gpt")}>
                  GPT
                </button>
                <button className={`btn ${tab === "service" ? "" : "secondary"}`} onClick={() => setTab("service")}>
                  Service
                </button>
                <button className={`btn ${tab === "backups" ? "" : "secondary"}`} onClick={() => setTab("backups")}>
                  Backups
                </button>
              </div>
            </div>
            {tab === "gpt" && <GptPanel gpt={gpt} busy={busy} onRead={onReadGpt} />}
            {tab === "service" && (
              <ServicePanel
                transport={transportRef.current!}
                log={(level, message) => pushLog(level, message)}
              />
            )}
            {tab === "backups" && (
              <BackupPanel
                transport={transportRef.current!}
                log={(level, message) => pushLog(level, message)}
              />
            )}
          </div>
        </div>
        <LogPanel entries={logs} onClear={() => setLogs([])} />
      </main>

      <footer className="footer">
        Mutations run the safety pipeline: plan → confirm token → auto-backup → execute →
        read-back verify. <span className="risk risk-red">red</span> ops additionally require an
        attestation and typed confirmation · <span className="risk risk-yellow">yellow</span> ops
        auto-backup first · everything is written to the session evidence log. Hardware paths are
        real but untested on physical devices — mock mode is clearly labelled.
      </footer>
    </div>
  );
}
