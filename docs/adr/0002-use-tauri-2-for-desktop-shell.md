# ADR-0002: Use Tauri 2 for the Desktop Shell

## Status

Accepted

## Date

2026-09-20

## Context

The Workbench requires a cross-platform desktop shell with native capabilities, a modern web UI, and lower resource overhead than a full bundled browser runtime where practical.

## Decision

Use Tauri 2 as the desktop application shell.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Small native shell.
- Strong fit for React/TypeScript UI.
- Native packaging and OS integration.

### Negative / trade-offs

- Adds Rust/Cargo to the contributor toolchain.
- Some desktop integrations require Tauri-specific knowledge.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
