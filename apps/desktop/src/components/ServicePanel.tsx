import { useState } from "react";
import type {
  MutationResult,
  OpPlan,
  PlanResponse,
  ServiceOpDef,
} from "../types";
import type { Transport } from "../transport";

const SERVICE_OPS: ServiceOpDef[] = [
  {
    method: "service.patch_modem",
    title: "Patch Modem",
    description:
      "Swap the vendor cert-verification modulus inside md1img (mtkclient patchmodem equivalent). Provide a replacement RSA-2048 key as PEM or raw modulus hex.",
    fields: [
      { name: "name", label: "Partition", def: "md1img" },
      { name: "new_modulus_hex", label: "New modulus (hex, 512 chars)", def: "", placeholder: "hex-encoded 256-byte modulus or leave empty and paste PEM below" },
      { name: "pem", label: "Replacement key (PEM, optional)", def: "", placeholder: "-----BEGIN PUBLIC KEY----- ..." },
    ],
  },
  {
    method: "service.patch_cert",
    title: "Patch Cert",
    description:
      "Composite cert workflow: auto-backup identity partitions (nvdata/nvram/protect1/protect2) + patch the modem cert modulus so certificate-based repair tools can attach.",
    fields: [
      { name: "new_modulus_hex", label: "New modulus (hex, 512 chars)", def: "" },
      { name: "pem", label: "Replacement key (PEM, optional)", def: "" },
    ],
  },
  {
    method: "service.unlock_bl",
    title: "Unlock Bootloader",
    description: "Write seccfg to the unlocked state (mtkclient seccfg 1). Wipes user data on next boot on most devices.",
    fields: [],
  },
  {
    method: "service.lock_bl",
    title: "Relock Bootloader",
    description: "Write seccfg to the locked state (mtkclient seccfg 0).",
    fields: [],
  },
  {
    method: "service.vbmeta_patch",
    title: "VBMeta Patch",
    description: "Disable Android Verified Boot verity/verification flags in the vbmeta partition.",
    fields: [{ name: "vbmode", label: "vbmode (1=verity 2=verify 3=both)", def: "3" }],
  },
  {
    method: "service.erase_frp",
    title: "Erase FRP",
    description: "Erase the factory reset protection partition (removes Google account lock after a wipe).",
    fields: [],
  },
  {
    method: "service.imei_read",
    title: "Read IMEI",
    description: "Decode the IMEI records from the nvdata NVItem block (read-only, green class).",
    fields: [],
    readOnly: true,
  },
  {
    method: "service.imei_write",
    title: "Write IMEI",
    description:
      "Restore-oriented identity write into the nvdata NVItem block (Luhn-checked). Red class: needs attestation and typed confirmation.",
    fields: [
      { name: "imei1", label: "IMEI 1 (15 digits)", def: "", placeholder: "490154203237518" },
      { name: "imei2", label: "IMEI 2 (optional)", def: "" },
    ],
  },
  {
    method: "partition.erase",
    title: "Erase Partition",
    description: "Erase an arbitrary partition by name (red class, always auto-backed-up first).",
    fields: [{ name: "name", label: "Partition name", def: "", placeholder: "frp" }],
  },
];

const RISK_COLOR: Record<string, string> = {
  green: "#1a7f37",
  yellow: "#9a6700",
  red: "#cf222e",
};

interface Props {
  transport: Transport;
  log: (level: string, message: string) => void;
}

export default function ServicePanel({ transport, log }: Props) {
  const [selected, setSelected] = useState<ServiceOpDef>(SERVICE_OPS[0]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [plan, setPlan] = useState<{ plan: OpPlan; token: string; params: Record<string, unknown> } | null>(null);
  const [attested, setAttested] = useState(false);
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<MutationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const paramsFor = (op: ServiceOpDef, extra: Record<string, unknown> = {}) => {
    const params: Record<string, unknown> = { ...extra };
    for (const f of op.fields) {
      const v = values[f.name] ?? f.def;
      if (v !== "") params[f.name] = v;
    }
    return params;
  };

  const selectOp = (op: ServiceOpDef) => {
    setSelected(op);
    setPlan(null);
    setResult(null);
    setError(null);
    setAttested(false);
    setTyped("");
    const init: Record<string, string> = {};
    for (const f of op.fields) init[f.name] = f.def;
    setValues(init);
  };

  const review = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const params = paramsFor(selected);
      const resp = (await transport.request(selected.method, { phase: "plan", ...params })) as unknown as PlanResponse;
      setPlan({ plan: resp.plan, token: resp.confirm_token, params });
      setAttested(false);
      setTyped("");
      log("info", `plan ready: ${resp.plan.summary} (risk=${resp.plan.risk})`);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const execute = async () => {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      const resp = (await transport.request(selected.method, {
        phase: "execute",
        ...plan.params,
        confirm_token: plan.token,
        ...(plan.plan.requires_attestation ? { attestation: true, typed_confirm: typed } : {}),
      })) as unknown as MutationResult;
      setResult(resp);
      setPlan(null);
      log("info", `${selected.method} executed (verified=${String(resp.verified)})`);
    } catch (err) {
      setError(String(err));
      log("error", `${selected.method}: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  };

  const canExecute =
    plan && (!plan.plan.requires_attestation || (attested && typed === "CONFIRM"));

  return (
    <div className="panel">
      <h2>Service Operations</h2>
      <p className="muted small">
        Every mutation runs the safety pipeline: plan → confirm token → auto-backup → execute →
        read-back verify. Red-class ops additionally require attestation and typing CONFIRM.
      </p>

      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div style={{ minWidth: 180 }}>
          {SERVICE_OPS.map((op) => (
            <button
              key={op.method}
              className={`op-item ${selected.method === op.method ? "active" : ""}`}
              onClick={() => selectOp(op)}
            >
              {op.title}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <h3>{selected.title}</h3>
          <p className="muted small">{selected.description}</p>

          {selected.fields.map((f) => (
            <label key={f.name} className="field">
              <span>{f.label}</span>
              <input
                value={values[f.name] ?? ""}
                placeholder={f.placeholder}
                onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              />
            </label>
          ))}

          {selected.readOnly ? (
            <button
              className="btn"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError(null);
                try {
                  const r = await transport.request(selected.method, {});
                  setResult({ phase: "executed", op: selected.method, risk: "green", backup_id: null, verified: true, ...r });
                } catch (err) {
                  setError(String(err));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Read
            </button>
          ) : (
            <button className="btn" disabled={busy} onClick={review}>
              Review plan…
            </button>
          )}

          {error && <div className="error-box">{error}</div>}

          {result && (
            <div className="result-box">
              <strong>Result</strong>{" "}
              {result.verified !== undefined && (
                <span className="badge" style={{ background: result.verified ? "#1a7f37" : "#cf222e" }}>
                  {result.verified ? "verified" : "unverified"}
                </span>
              )}
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>

      {plan && (
        <div className="dialog-backdrop" onClick={() => !busy && setPlan(null)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Confirm operation</h3>
            <div>
              <span className="badge" style={{ background: RISK_COLOR[plan.plan.risk] ?? "#666" }}>
                {plan.plan.risk} risk
              </span>
            </div>
            <p>
              <strong>{plan.plan.summary}</strong>
            </p>
            <div className="muted small">
              Changes:
              <ul>
                {plan.plan.changes.map((c, i) => (
                  <li key={i}>{JSON.stringify(c)}</li>
                ))}
              </ul>
              Auto-backup before execute:{" "}
              <strong>{plan.plan.backup_partitions.length ? plan.plan.backup_partitions.join(", ") : "(none)"}</strong>
            </div>

            {plan.plan.requires_attestation && (
              <div className="attest-box">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={attested}
                    onChange={(e) => setAttested(e.target.checked)}
                  />
                  <span>
                    I confirm I am the legal owner / authorized servicer of this device and accept
                    responsibility for this change.
                  </span>
                </label>
                <label className="field">
                  <span>
                    Type <code>CONFIRM</code> to proceed
                  </span>
                  <input value={typed} onChange={(e) => setTyped(e.target.value)} />
                </label>
              </div>
            )}

            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="btn" disabled={!canExecute || busy} onClick={execute}>
                {busy ? "Working…" : "Execute"}
              </button>
              <button className="btn secondary" disabled={busy} onClick={() => setPlan(null)}>
                Cancel
              </button>
            </div>
            <p className="muted small">
              confirm_token: <code>{plan.token}</code> — bound to these exact parameters; any
              change requires a new plan.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
