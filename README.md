# Skoiv MTK Workbench

An open-source, evidence-driven MediaTek recovery, diagnostics, backup, firmware-analysis, and learning workbench built around mtkclient.

## Product principles

- Safety first.
- Evidence over assumptions.
- Read before write.
- Backup before modification.
- Explain every conclusion.
- Preserve raw evidence beside every abstraction.
- Show the exact operation before execution.
- Verify writes by read-back before declaring success.
- Keep advanced control available without making risky actions casual.
- Preserve user and community freedom in distributed derivatives.

## Planned stack

- Desktop shell: Tauri 2
- UI: React + TypeScript + Vite
- TypeScript package manager: pnpm
- Python worker: Python + uv
- Rust package manager: Cargo
- MTK engine: mtkclient behind a Workbench-owned adapter
- Desktop/worker IPC: structured JSON messages over stdio

## Current status

The 0.1 vertical slice is implemented: Python worker (IPC v1, GPT parser with
evidence hashes, mock + mtkclient adapters), Tauri 2 desktop shell with the
React UI, PyInstaller sidecar packaging, and a GitHub Actions pipeline that
builds the Windows NSIS installer (`release-windows.yml`). The UI can be run
against a browser mock (`pnpm dev`) or the real worker (`pnpm tauri dev`).

See `worker/README.md`, `apps/desktop/README.md`, and
`docs/development/release.md` for development and release workflows.

## v0.1 boundary

Version 0.1 is intentionally read-only with respect to device partitions. Its core capabilities are planned to include device detection, GPT inspection, selective BROM backup, preloader inspection/splitting, DA inspection, firmware-package inspection, firmware consistency checks, command preview, persistent logs, evidence capture, sessions, and learning content.

## License

Skoiv MTK Workbench is licensed under the **GNU General Public License v3.0 only** (`GPL-3.0-only`). See `LICENSE` and `docs/adr/0013-license-skoiv-mtk-workbench-under-gplv3.md`.

Commercial use is allowed. The GPL is about preserving software freedom, not prohibiting paid use or services. Covered modified versions that are distributed must comply with the GPLv3 terms, including applicable corresponding-source and notice requirements.

Third-party components retain their own licenses. In particular, mtkclient remains under its upstream GPLv3 license and copyright; Skoiv Labs does not relicense it.

See `PROJECT_VISION.md`, `ROADMAP.md`, `SAFETY_POLICY.md`, and `docs/adr/`.
