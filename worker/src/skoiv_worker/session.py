"""Persistent session evidence ledger (ADR-0009/0010).

Every mutating operation and its verification outcome is appended to a JSONL
session file under sessions/local/ (gitignored). Sessions are the exportable
evidence trail: what was planned, what changed, and how it was verified.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any


class SessionLedger:
    def __init__(self, root: str | None = None) -> None:
        self.root = root or os.environ.get("SKOIV_SESSION_ROOT") or os.path.join(os.getcwd(), "sessions", "local")
        self._lock = threading.Lock()
        self._path: str | None = None

    @property
    def path(self) -> str | None:
        return self._path

    def append(self, kind: str, payload: dict[str, Any]) -> None:
        record = {"ts": time.time(), "kind": kind, "payload": payload}
        with self._lock:
            if self._path is None:
                os.makedirs(self.root, exist_ok=True)
                ts = time.strftime("%Y%m%d-%H%M%S")
                self._path = os.path.join(self.root, f"session-{ts}.jsonl")
            try:
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, default=str) + "\n")
            except OSError:
                # Evidence persistence must never break device operations.
                pass
