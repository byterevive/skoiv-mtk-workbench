# ADR-0007: Version 0.1 is Device Read-Only

## Status

Accepted

## Date

2026-09-20

## Context

Early development will be used on real devices while the architecture and safety model are still maturing.

## Decision

Version 0.1 may read device information and partitions, but it must not expose partition erase or write operations.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Significantly lowers device risk during early development.
- Lets backup and inspection mature first.

### Negative / trade-offs

- Users cannot perform repairs that require writes until a later release.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
