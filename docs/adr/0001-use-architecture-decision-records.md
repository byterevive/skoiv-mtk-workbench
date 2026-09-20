# ADR-0001: Use Architecture Decision Records

## Status

Accepted

## Date

2026-09-20

## Context

The project is intended to be long-lived, open source, safety-sensitive, and maintained by contributors who will not share the original design context.

## Decision

Use ADRs from the beginning of the project. Accepted records remain historical records; later changes create new ADRs and mark old records as superseded or deprecated.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Architectural reasoning survives contributor turnover.
- Safety decisions remain explainable.
- Major changes can be reviewed in context.

### Negative / trade-offs

- Adds documentation work.
- Requires discipline to keep status links current.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
