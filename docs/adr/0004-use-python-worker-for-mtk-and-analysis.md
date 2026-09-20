# ADR-0004: Use a Python Worker for MTK and Analysis

## Status

Accepted

## Date

2026-09-20

## Context

mtkclient and much of the expected binary-analysis ecosystem are Python-friendly. Reimplementing MediaTek communication in Rust would expand scope significantly.

## Decision

Use a dedicated Python worker for mtkclient integration, parsers, backup orchestration, hashing, and analysis.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Reuses mtkclient naturally.
- Good binary-processing ecosystem.
- Keeps device logic isolated from UI.

### Negative / trade-offs

- Application ships or manages two language runtimes.
- Worker lifecycle and IPC require careful design.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
