interface Props {
  workerStatus: "starting" | "ready" | "error" | "stopped";
  transportMode: "tauri" | "mock";
  adapterName: string;
  workerVersion: string;
}

const STATUS_LABEL: Record<Props["workerStatus"], string> = {
  starting: "Worker starting…",
  ready: "Worker ready",
  error: "Worker error",
  stopped: "Worker stopped",
};

export default function StatusBar({ workerStatus, transportMode, adapterName, workerVersion }: Props) {
  return (
    <header className="statusbar">
      <div className="brand">
        <img src="/app-icon.png" alt="" className="brand-icon" width={32} height={32} />
        <div>
          <h1>Skoiv MTK Workbench</h1>
          <span className="brand-sub">Evidence-driven MediaTek recovery &amp; diagnostics</span>
        </div>
      </div>
      <div className="status-chips">
        <span className={`chip status-${workerStatus}`}>
          <span className="led" />
          {STATUS_LABEL[workerStatus]}
        </span>
        <span className="chip">adapter: {adapterName || "—"}</span>
        <span className="chip">{transportMode === "tauri" ? "desktop shell" : "browser preview (mock)"}</span>
        <span className="chip chip-dim">worker {workerVersion || "—"}</span>
        <span className="chip chip-dim">v0.1 read-only</span>
      </div>
    </header>
  );
}
