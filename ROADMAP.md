# Roadmap

## 0.1 — Observe

Read, inspect, understand, and back up.

- Desktop shell and Python worker lifecycle
- Structured stdio IPC
- Persistent session logging
- Device-state detection
- GPT/partition viewer
- Selective BROM backup
- Backup manifests and SHA-256 verification
- Preloader Lab
- DA Inspector
- Firmware Package Inspector
- Firmware Consistency Checker
- Read-only Command Studio
- Learn center and persistent tabs
- Evidence provenance

## 0.2 — Modify Safely

- Controlled writes — **implemented** (plan → confirm token → execute; `partition.write|erase`, patch/IMEI/seccfg/vbmeta ops)
- Safety-engine gating — **implemented** (risk classes green/yellow/red, boot-critical escalation, attestation + typed CONFIRM for red ops)
- Mandatory pre-write review for risky operations — **implemented** (two-phase plan/confirm dialog bound to exact parameters)
- Backup requirements — **implemented** (auto-backup of affected partitions before every mutation; `backups/` with SHA-256 manifests)
- Read-back verification — **implemented** (post-write read-back + hash compare, session JSONL evidence log)
- Boot-critical operation protections — **implemented** (boot-critical targets escalate to red)
- Patch Modem / Patch Cert (md1img modulus swap) — **implemented** (hardware path untested)
- IMEI read/write (nvdata NVItems) — **implemented** (hardware path untested)
- Flash tool (scatter images, staged flash) — pending

## 0.3 — Knowledge

- Community compatibility repository
- Evidence-backed DA/preloader pair records
- Device profiles
- Maintainer review workflow
- Safe artifact referencing by hashes and official sources

## 0.4 — Recover

- Guided recovery workflows
- Failure-stage interpretation
- Context-sensitive suggestions
- Diagnostic bundle export

## 1.0 — Stable Workbench

- Stable cross-platform application
- Versioned public data formats
- Mature safety policy
- Documented migration paths
