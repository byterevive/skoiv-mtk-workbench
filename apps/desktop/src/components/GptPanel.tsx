import type { GptResult, Risk } from "../types";
import { formatBytes, formatLba } from "../format";

interface Props {
  gpt: GptResult | null;
  busy: boolean;
  onRead: () => void;
}

function RiskBadge({ risk }: { risk: Risk }) {
  return <span className={`risk risk-${risk}`}>{risk}</span>;
}

export default function GptPanel({ gpt, busy, onRead }: Props) {
  return (
    <section className="panel panel-grow">
      <div className="panel-head">
        <h2>GPT / partition table</h2>
        <button className="btn" onClick={onRead} disabled={busy}>
          {busy ? "Reading…" : "Read GPT"}
        </button>
      </div>

      {gpt === null && (
        <p className="hint">
          Read the GUID partition table to inspect partition layout. Raw bytes are hashed
          (SHA-256) and CRC checks are reported so every conclusion stays evidence-backed.
        </p>
      )}

      {gpt !== null && (
        <>
          <div className="gpt-summary">
            <span className="chip">
              source: <span className="mono">{gpt.source}</span>
            </span>
            <span className={`chip ${gpt.header_crc32_ok ? "chip-ok" : "chip-bad"}`}>
              header CRC {gpt.header_crc32_ok ? "valid" : "MISMATCH"}
            </span>
            <span className={`chip ${gpt.entries_crc32_ok ? "chip-ok" : "chip-bad"}`}>
              entries CRC {gpt.entries_crc32_ok ? "valid" : "MISMATCH"}
            </span>
            <span className="chip chip-dim">
              {gpt.partitions.length} partitions · sector {gpt.sector_size} B
            </span>
            <span className="chip chip-dim mono" title={gpt.raw_sha256}>
              sha256 {gpt.raw_sha256.slice(0, 16)}…
            </span>
            <span className="chip chip-dim mono" title={gpt.disk_guid}>
              disk {gpt.disk_guid.slice(0, 8)}…
            </span>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th className="num">First LBA</th>
                  <th className="num">Last LBA</th>
                  <th className="num">Size</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {gpt.partitions.map((p) => (
                  <tr key={p.index}>
                    <td className="mono dim">{p.index}</td>
                    <td className="mono">{p.name}</td>
                    <td className="dim">{p.type_name}</td>
                    <td className="num mono">{formatLba(p.first_lba)}</td>
                    <td className="num mono">{formatLba(p.last_lba)}</td>
                    <td className="num mono">{formatBytes(p.size_bytes)}</td>
                    <td>
                      <RiskBadge risk={p.risk} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
