# ADR-0009: Preserve Raw Evidence alongside Abstractions

## Status

Accepted

## Date

2026-09-20

## Context

Parsers and friendly UI can be wrong. Users and maintainers need to trace conclusions back to bytes, logs, metadata, or device responses.

## Decision

Every meaningful parsed conclusion should retain provenance to its raw source where feasible.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Builds trust.
- Enables debugging parser mistakes.
- Supports the project's "show why" principle.

### Negative / trade-offs

- Provenance increases data-model complexity and storage usage.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
