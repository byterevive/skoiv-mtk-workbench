# Python Worker

The Skoiv Python worker owns mtkclient integration (behind the Workbench
adapter boundary, ADR-0006), binary parsing, hashing, and evidence generation.
It speaks IPC v1 (structured JSON, one object per line) over stdio.

## Layout

```text
worker/
├── src/skoiv_worker/
│   ├── __main__.py        # stdio loop entrypoint (python -m skoiv_worker)
│   ├── protocol.py        # IPC v1 envelope (schemas/ipc/v1/)
│   ├── service.py         # request dispatch
│   ├── gpt.py             # GPT parsing + risk classification + evidence hashes
│   └── adapters/
│       ├── base.py        # Workbench-owned adapter contract
│       ├── mock.py        # deterministic fixture device (tests/dev)
│       └── mtkclient_adapter.py  # real device access via mtkclient (read-only)
├── tests/                 # pytest suite (no hardware required)
├── skoiv-worker.spec      # PyInstaller bundle definition
└── skoiv_worker_entry.py  # frozen-build entrypoint
```

## Development

```bash
cd worker
uv sync --extra dev             # core + tests (mock adapter)
uv sync --extra dev --extra device  # + mtkclient + libusb (real device support)
uv run python -m pytest -q
echo '{"v":1,"type":"request","id":"1","method":"ping","params":{}}' \
  | uv run python -m skoiv_worker --adapter mock
```

Adapter selection: `--adapter auto|mock|mtkclient` (default `auto` =
mtkclient when installed, otherwise mock). `SKOIV_MOCK=1` forces mock mode.

## Notes

- mtkclient is **not on PyPI**; it is pinned from its GPLv3 upstream via the
  `device` extra. PySide6/shiboken6 (its optional GUI) are stripped by uv
  dependency overrides — the worker is headless.
- `libusb-package` vendors the libusb shared library pyusb needs at runtime;
  the worker seeds pyusb's backend with it (`_ensure_libusb`).
- The frozen Windows build (`skoiv-worker.exe`) is produced by the
  `release-windows` workflow via `skoiv-worker.spec`.
- Version 0.1 issues **reads only** (ADR-0007). There are no write or erase
  methods in the protocol.
