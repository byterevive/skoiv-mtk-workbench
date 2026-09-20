# Architecture Decision Records

Architecture Decision Records (ADRs) preserve the reasoning behind important project decisions.

## Statuses

- **Proposed** — under discussion and not yet binding.
- **Accepted** — current architectural decision.
- **Superseded by ADR-XXXX** — replaced by a newer decision. Keep the old ADR for history.
- **Deprecated** — no longer recommended/current, but not necessarily replaced by one specific ADR.
- **Rejected** — considered and intentionally not adopted.

## Replacement rule

Do not rewrite an accepted ADR to pretend a later decision was always the design.

When a newer ADR replaces an older one:

1. Create a new ADR with a new number.
2. Set the old ADR status to `Superseded by ADR-XXXX` when the replacement is direct.
3. Use `Deprecated` when the old decision is retired without one exact replacement.
4. Add `Supersedes: ADR-XXXX` to the new ADR.
5. Keep both files in Git history and in this directory.

This gives contributors a chronological explanation of how and why the architecture evolved.

## When an ADR is required

Create an ADR when a decision significantly affects architecture, safety, compatibility, maintainability, persistent data formats, IPC/public interfaces, security boundaries, operating-system support, or contributor behavior.

Do not create ADRs for ordinary refactors, naming changes, icon choices, or small visual tweaks.

## Naming

`NNNN-short-kebab-title.md`

Examples:

- `0005-use-json-messages-over-stdio.md`
- `0013-version-backup-manifest-schema.md`

## Template

Copy `template.md`, assign the next number, and fill every relevant section.
