# ADR-0006: Access mtkclient through an Adapter

## Status

Accepted

## Date

2026-09-20

## Context

Direct use of mtkclient CLI or internals throughout the application would couple product workflows to upstream implementation details.

## Decision

All mtkclient interactions go through a Workbench-owned adapter boundary.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Upstream changes are isolated.
- Enables mocks and tests.
- Centralizes safety, logging, and command translation.

### Negative / trade-offs

- Adds an abstraction layer.
- New mtkclient features need adapter support.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
