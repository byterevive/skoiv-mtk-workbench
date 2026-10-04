import type { DetectResult } from "../types";
import { formatHex16 } from "../format";

interface Props {
  detect: DetectResult | null;
  busy: boolean;
  onDetect: () => void;
}

export default function DevicePanel({ detect, busy, onDetect }: Props) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Device detection</h2>
        <button className="btn" onClick={onDetect} disabled={busy}>
          {busy ? "Detecting…" : "Detect device"}
        </button>
      </div>

      {detect === null && (
        <p className="hint">
          No detection run yet. Connect a powered-off MediaTek device while holding the volume keys
          (BROM/preloader mode), then run detection.
        </p>
      )}

      {detect !== null && detect.devices.length === 0 && (
        <div className="empty">
          <p>No MediaTek target found.</p>
          {detect.hint && <p className="hint">{detect.hint}</p>}
        </div>
      )}

      {detect !== null &&
        detect.devices.map((d) => (
          <div className="device-row" key={d.port}>
            <div className="device-mode">{d.mode ?? "unknown"}</div>
            <div className="device-info">
              <strong>{d.chip_hint ?? "MediaTek target"}</strong>
              <span className="mono">{d.port}</span>
              <span className="hint">{d.description}</span>
            </div>
            <div className="device-ids mono">
              {formatHex16(d.vid)}:{formatHex16(d.pid)}
            </div>
          </div>
        ))}
    </section>
  );
}
