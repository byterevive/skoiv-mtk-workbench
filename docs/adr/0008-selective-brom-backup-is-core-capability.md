# ADR-0008: Selective BROM Backup is a Core Capability

## Status

Accepted

## Date

2026-09-20

## Context

Recovery work can destroy unique calibration, identity, and user-relevant partitions. BROM-level reads provide a valuable opportunity to preserve data before modification.

## Decision

Treat selective BROM partition backup as a core product capability, with partition selection, presets, hashing, manifests, and verification.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Makes safety practical, not advisory.
- Supports targeted backups without forcing full-device dumps.
- Produces reusable evidence.

### Negative / trade-offs

- Partition meaning differs across devices and cannot be blindly hard-coded.
- Large reads require robust progress and storage handling.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
