# ADR-0003: Use React, TypeScript, and Vite for the UI

## Status

Accepted

## Date

2026-09-20

## Context

The UI will contain stateful workspaces, tabs, logs, inspectors, learning views, evidence panes, and long-running operation state.

## Decision

Use React with TypeScript and Vite for the desktop UI.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Mature ecosystem and strong stateful UI model.
- TypeScript improves contracts.
- Vite provides fast development tooling.

### Negative / trade-offs

- Web UI complexity must be kept under control.
- Requires frontend dependency management.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
