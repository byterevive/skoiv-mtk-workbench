# ADR-0005: Use JSON Messages over stdio

## Status

Accepted

## Date

2026-09-20

## Context

The desktop app needs local communication with its Python worker without opening network ports or introducing an HTTP server for a local desktop workflow.

## Decision

Use structured JSON messages over stdio for desktop-to-worker IPC in the initial architecture.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- No localhost port or firewall surface.
- Worker lifecycle can be owned by the desktop shell.
- Messages can be logged and tested.

### Negative / trade-offs

- Requires framing and protocol discipline.
- Long-running operations and streaming need explicit message types.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
