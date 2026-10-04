# Release Process

## Windows exe release

Releases are built on GitHub Actions (`windows-latest`) by
`.github/workflows/release-windows.yml`. Nothing about the Windows build needs
to run on a developer machine.

### Pipeline

1. Python worker deps install with `uv sync --extra dev --extra device`
   (includes pinned mtkclient + libusb-package).
2. Worker tests run (fixture-based, no hardware).
3. `skoiv-worker.spec` freezes the worker into `skoiv-worker.exe` with
   PyInstaller (one-file, headless; Qt/FUSE excluded).
4. The exe is placed at
   `apps/desktop/src-tauri/binaries/skoiv-worker-x86_64-pc-windows-msvc.exe`
   so Tauri picks it up as a sidecar (`bundle.externalBin`).
5. `pnpm tauri build` produces the NSIS installer
   (`*-setup.exe` in `src-tauri/target/release/bundle/nsis/`).
6. Artifacts are checksummed (`SHA256SUMS.txt`).

### Cutting a release

```bash
git tag v0.1.0
git push origin v0.1.0
```

The tag push triggers the workflow, which attaches the installer, the
standalone worker exe, and checksums to a GitHub Release. A manual
`workflow_dispatch` run builds the same artifacts without publishing.

### End-user prerequisites (Windows)

- **USB driver**: the MediaTek BROM/preloader interface must be bound to
  WinUSB/libusbK (e.g. via Zadig). Document this in the release notes —
  it cannot be automated from the installer.
- **Unsigned binary**: without a code-signing certificate SmartScreen shows a
  warning. Code signing is a future consideration.

### License obligations (GPL-3.0-only)

The distributed bundle contains GPLv3 components (the Workbench itself,
mtkclient, PyInstaller's bootloader). Each release must make corresponding
source available: link this repository at the release tag (GitHub's source
archives) and the pinned `bkerler/mtkclient` tag. The release workflow's
notes template covers this.

## Versioning

`worker/src/skoiv_worker/__init__.py`, `apps/desktop/package.json`, and
`apps/desktop/src-tauri/tauri.conf.json` carry the version; keep them in sync
when tagging. The IPC protocol version (`v: 1`) is independent and only
changes with a schema update in `schemas/ipc/`.
