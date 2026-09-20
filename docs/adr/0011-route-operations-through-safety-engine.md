# ADR-0011: Route Operations through a Safety Engine

## Status

Accepted

## Date

2026-09-20

## Context

Future versions will introduce write and boot-critical operations. Allowing UI components or templates to call the MTK adapter directly would make safety bypasses easy.

## Decision

All operations must pass through a Workbench operation and safety layer before reaching device adapters.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Central safety enforcement.
- Consistent risk classification and confirmations.
- Easier audit logging.

### Negative / trade-offs

- Adds orchestration complexity even for simple operations.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
