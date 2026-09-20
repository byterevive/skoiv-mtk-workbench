# ADR-0010: Use Structured and Raw Persistent Logging

## Status

Accepted

## Date

2026-09-20

## Context

Recovery failures often happen during disconnects, crashes, or hangs. In-memory-only logs are insufficient, and clean UI logs must not replace original tool output.

## Decision

Persist structured events and raw underlying output, stream them to a VS Code-style log panel, and keep logs recoverable across crashes.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Better diagnostics and reproducibility.
- Supports filtering without losing raw lines.
- Survives UI or worker failures more reliably.

### Negative / trade-offs

- Requires log rotation, retention, privacy handling, and efficient rendering.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
