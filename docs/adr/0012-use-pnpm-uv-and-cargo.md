# ADR-0012: Use pnpm, uv, and Cargo

## Status

Accepted

## Date

2026-09-20

## Context

The project spans TypeScript, Python, and Rust. Each ecosystem needs reproducible dependency management without adding unnecessary monorepo tooling at project start.

## Decision

Use pnpm for TypeScript workspaces, uv for Python dependencies and environments, and Cargo for Rust/Tauri. Do not add Nx or Turborepo initially.

## Alternatives considered

Alternatives were considered during project planning. Future changes should create a new ADR rather than rewriting this record.

## Consequences

### Positive

- Uses strong native tooling in each ecosystem.
- Keeps early monorepo orchestration simple.
- Provides reproducible lockfiles.

### Negative / trade-offs

- Contributors install multiple toolchains.
- Root-level orchestration must provide a friendly setup experience.

## Safety impact

This decision must preserve the project safety principles in `SAFETY_POLICY.md`.

## Supersedes

None

## Superseded by

None

## Related ADRs

See the ADR index in `docs/adr/INDEX.md`.
