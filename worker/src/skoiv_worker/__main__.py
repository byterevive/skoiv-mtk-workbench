"""Worker entrypoint: JSON-line stdio loop.

Usage:
    python -m skoiv_worker [--adapter auto|mock|mtkclient] [--stdio]

The desktop shell spawns this as a sidecar process (PyInstaller build named
``skoiv-worker``) and exchanges one JSON object per line over stdin/stdout.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .adapters import create_adapter
from .protocol import (
    MessageWriter,
    ProtocolError,
    make_error,
    make_log,
    make_response,
    parse_message,
)
from .service import Service


def run_stdio(adapter_kind: str) -> int:
    # Keep the JSON stream pristine: anything the worker (or mtkclient) prints
    # must not interleave with protocol messages on stdout.
    raw_stdout = sys.stdout
    sys.stdout = sys.stderr if sys.stderr is not None else raw_stdout

    writer = MessageWriter(raw_stdout)
    adapter = create_adapter(adapter_kind)
    service = Service(adapter, emit=writer.write)

    writer.write(make_log("info", f"skoiv-worker {__version__} started", adapter=adapter.name))
    writer.write(
        {
            "v": 1,
            "type": "event",
            "event": "worker-health",
            "data": {"status": "ready", "adapter": adapter.name},
        }
    )

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = parse_message(line)
        except ProtocolError as exc:
            writer.write(make_error("", "protocol-error", str(exc)))
            continue

        if parsed.kind != "request" or parsed.request is None:
            # The worker only accepts requests; ignore stray messages.
            continue

        req = parsed.request
        response = service.handle_request(req.id, req.method, req.params)
        writer.write(response)

        if req.method == "shutdown":
            break

    writer.write(make_log("info", "skoiv-worker exiting"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skoiv-worker", description="Skoiv MTK Workbench Python worker")
    parser.add_argument(
        "--adapter",
        choices=("auto", "mock", "mtkclient"),
        default="auto",
        help="device adapter (auto: mtkclient when installed, else mock fixture)",
    )
    parser.add_argument("--stdio", action="store_true", help="run the JSON-line stdio loop (default)")
    parser.add_argument("--version", action="version", version=f"skoiv-worker {__version__}")
    args = parser.parse_args(argv)

    return run_stdio(args.adapter)


if __name__ == "__main__":
    sys.exit(main())
