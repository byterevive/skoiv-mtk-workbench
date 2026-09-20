# Safety Policy

Safety is a product requirement, not an optional warning layer.

## Baseline rules

- Read-only operations are the default in 0.1.
- Never erase or write implicitly.
- Never hide the exact target partition or operation.
- Preserve original evidence and logs.
- Require explicit review before future write operations.
- Back up critical data before future modification workflows.
- Treat boot-critical partitions as elevated risk.
- Prefer read-back verification after any future write.
- Do not encourage blind flashing based only on device-name similarity.

## Risk classes

### Green — Read only

Examples: identify device, read GPT, read partition, hash files, inspect firmware, inspect DA, inspect preloader.

### Yellow — Controlled modification

Examples: future writes to ordinary boot/runtime partitions. Requires validation, backup policy checks, confirmation, and read-back verification.

### Red — Boot critical

Examples: preloader, GPT, LK, TEE, SSPM, SPMFW, boot regions, erase/format operations. These require additional gating and must never appear as casual one-click actions.
