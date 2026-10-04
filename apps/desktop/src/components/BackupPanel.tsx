import { useCallback, useEffect, useState } from "react";
import type { BackupManifest, MutationResult } from "../types";
import type { Transport } from "../transport";

interface Props {
  transport: Transport;
  log: (level: string, message: string) => void;
}

const PRESETS = [
  { id: "identity", label: "Identity (nvdata/nvram/protect*)" },
  { id: "critical", label: "Boot-critical (preloader/lk/boot…)" },
  { id: "servicing", label: "Servicing set" },
];

export default function BackupPanel({ transport, log }: Props) {
  const [backups, setBackups] = useState<BackupManifest[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<BackupManifest | null>(null);
  const [typed, setTyped] = useState("");
  const [attested, setAttested] = useState(false);
  const [result, setResult] = useState<MutationResult | null>(null);

  const refresh = useCallback(async () => {
    try {
      const resp = (await transport.request("backup.list", {})) as unknown as { backups: BackupManifest[] };
      setBackups(resp.backups ?? []);
    } catch (err) {
      setError(String(err));
    }
  }, [transport]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const create = async (preset: string) => {
    setBusy(true);
    setError(null);
    try {
      const manifest = (await transport.request("backup.create", { preset })) as unknown as BackupManifest;
      log("info", `backup created: ${manifest.backup_id}`);
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const restore = async () => {
    if (!restoreTarget) return;
    setBusy(true);
    setError(null);
    try {
      const planResp = (await transport.request("backup.restore", {
        phase: "plan",
        backup_id: restoreTarget.backup_id,
      })) as unknown as { confirm_token: string };
      const resp = (await transport.request("backup.restore", {
        phase: "execute",
        backup_id: restoreTarget.backup_id,
        confirm_token: planResp.confirm_token,
        attestation: true,
        typed_confirm: typed,
      })) as unknown as MutationResult;
      setResult(resp);
      setRestoreTarget(null);
      setTyped("");
      setAttested(false);
      log("info", `restore complete: ${restoreTarget.backup_id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <h2>Backups</h2>
      <p className="muted small">
        Local partition backups with SHA-256 manifests (<code>backups/</code>, gitignored). Every
        mutating operation auto-backs-up its targets first.
      </p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {PRESETS.map((p) => (
          <button key={p.id} className="btn" disabled={busy} onClick={() => create(p.id)}>
            {p.label}
          </button>
        ))}
        <button className="btn secondary" disabled={busy} onClick={refresh}>
          Refresh
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {result && (
        <div className="result-box">
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>Backup</th>
            <th>Partitions</th>
            <th>Created</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {backups.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                No backups yet.
              </td>
            </tr>
          )}
          {backups.map((b) => (
            <tr key={b.backup_id}>
              <td>
                <code>{b.backup_id}</code>
                {b.note && <div className="muted small">{b.note}</div>}
              </td>
              <td className="small">{Object.keys(b.partitions).join(", ")}</td>
              <td className="small">{new Date(b.created * 1000).toLocaleString()}</td>
              <td>
                <button className="btn secondary" disabled={busy} onClick={() => { setRestoreTarget(b); setAttested(false); setTyped(""); }}>
                  Restore…
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {restoreTarget && (
        <div className="dialog-backdrop" onClick={() => !busy && setRestoreTarget(null)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Restore backup</h3>
            <p>
              <span className="badge" style={{ background: "#cf222e" }}>red risk</span>{" "}
              Overwrite current partitions from <code>{restoreTarget.backup_id}</code>.
            </p>
            <label className="check">
              <input type="checkbox" checked={attested} onChange={(e) => setAttested(e.target.checked)} />
              <span>I am the legal owner / authorized servicer and accept responsibility.</span>
            </label>
            <label className="field">
              <span>
                Type <code>CONFIRM</code> to proceed
              </span>
              <input value={typed} onChange={(e) => setTyped(e.target.value)} />
            </label>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button
                className="btn"
                disabled={busy || !attested || typed !== "CONFIRM"}
                onClick={restore}
              >
                {busy ? "Working…" : "Restore"}
              </button>
              <button className="btn secondary" disabled={busy} onClick={() => setRestoreTarget(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
