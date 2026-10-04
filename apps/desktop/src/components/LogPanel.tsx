import type { LogEntry } from "../types";

interface Props {
  entries: LogEntry[];
  onClear: () => void;
}

export default function LogPanel({ entries, onClear }: Props) {
  return (
    <section className="panel panel-log">
      <div className="panel-head">
        <h2>Evidence log</h2>
        <button className="btn btn-ghost" onClick={onClear}>
          Clear
        </button>
      </div>
      <div className="log">
        {entries.length === 0 && <p className="hint">Worker events and operation evidence appear here.</p>}
        {entries.map((e) => (
          <div key={e.id} className={`log-line log-${e.level}`}>
            <span className="log-ts">
              {new Date(e.ts * 1000).toLocaleTimeString("en-US", { hour12: false })}
            </span>
            <span className="log-level">{e.level}</span>
            <span className="log-msg">{e.message}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
