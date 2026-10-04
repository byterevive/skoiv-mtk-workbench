"""End-to-end stdio loop tests (subprocess, JSON lines)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_session(requests):
    env = dict(os.environ)
    env["SKOIV_MOCK"] = "1"
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    proc = subprocess.Popen(
        [sys.executable, "-m", "skoiv_worker", "--adapter", "mock"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=ROOT,
        env=env,
    )
    lines = [json.dumps(r) for r in requests]
    out, err = proc.communicate("\n".join(lines) + "\n", timeout=30)
    messages = [json.loads(line) for line in out.splitlines() if line.strip()]
    return proc.returncode, messages, err


def test_stdio_session():
    req_ping = {"v": 1, "type": "request", "id": "p1", "method": "ping", "params": {}}
    req_gpt = {"v": 1, "type": "request", "id": "g1", "method": "gpt.read", "params": {}}
    req_bad = "{broken"
    req_off = {"v": 1, "type": "request", "id": "s1", "method": "shutdown", "params": {}}

    code, messages, err = run_session([req_ping, req_gpt, req_bad, req_off])

    assert code == 0, err
    responses = {m.get("id"): m for m in messages if m.get("type") == "response"}
    assert responses["p1"]["ok"] is True
    assert responses["g1"]["ok"] is True
    assert responses["g1"]["result"]["source"] == "mock:fixture"
    assert responses["s1"]["result"]["bye"] is True

    # Malformed input yields a protocol-error response, not a crash.
    assert responses[""]["error"]["code"] == "protocol-error"

    health = [m for m in messages if m.get("event") == "worker-health"]
    assert health and health[0]["data"]["status"] == "ready"


def test_stdio_reports_events():
    req_gpt = {"v": 1, "type": "request", "id": "g1", "method": "gpt.read", "params": {}}
    req_off = {"v": 1, "type": "request", "id": "s1", "method": "shutdown", "params": {}}
    _, messages, _ = run_session([req_gpt, req_off])
    events = {m.get("event") for m in messages if m.get("type") == "event"}
    assert {"worker-health", "log", "operation-started", "operation-completed"} <= events
