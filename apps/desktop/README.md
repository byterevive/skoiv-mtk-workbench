# Desktop App

Tauri 2 + React + TypeScript + Vite desktop shell (ADR-0002, ADR-0003).

## Layout

```text
apps/desktop/
├── src/                   # React UI (device panel, GPT viewer, evidence log)
├── src-tauri/
│   ├── src/main.rs        # app entry
│   ├── src/worker.rs      # worker lifecycle + stdio request/response bridge
│   ├── tauri.conf.json    # window/bundle config, sidecar declaration
│   ├── binaries/          # skoiv-worker-$TRIPLE sidecar (built by CI; gitignored)
│   └── icons/
└── scripts/generate_icons.py
```

## Development

```bash
pnpm install          # repo root (pnpm workspace)
pnpm dev              # Vite dev server on :5173 — full UI with browser mock transport
pnpm tauri dev        # native shell (requires Rust toolchain + webkit2gtk on Linux)
```

In a plain browser the UI runs against an embedded mock transport (fixture
device + GPT) so every panel is explorable without hardware. Inside the Tauri
shell the UI talks to the Python worker over structured JSON/stdio (IPC v1).

The shell spawns `skoiv-worker` as a Tauri sidecar (`bundle.externalBin`). For
local native development without the frozen binary, set `SKOIV_WORKER_BIN` and
`SKOIV_WORKER_ARGS` (e.g. `SKOIV_WORKER_BIN=uv SKOIV_WORKER_ARGS="run python -m skoiv_worker --adapter mock"`
run from the `worker/` directory).

## Release builds

The Windows NSIS installer is produced by `.github/workflows/release-windows.yml`.
See `docs/development/release.md`.
