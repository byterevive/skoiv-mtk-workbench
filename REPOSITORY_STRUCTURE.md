# Repository Structure

```text
skoiv-mtk-workbench/
├── .github/
├── apps/
│   └── desktop/
├── worker/
├── packages/
├── docs/
│   ├── adr/
│   ├── architecture/
│   ├── development/
│   ├── product/
│   └── safety/
├── knowledge/
│   ├── brom/
│   ├── da/
│   ├── emi/
│   ├── preloader/
│   └── recovery/
├── repository/
│   ├── devices/
│   └── submissions/
├── schemas/
├── tests/
├── assets/
├── templates/
├── examples/
└── sessions/
```

## Separation of responsibilities

- `docs/adr/`: why major decisions were made.
- `docs/architecture/`: how the current system is intended to work.
- `docs/product/`: product behavior and UX contracts.
- `docs/safety/`: safety constraints and risk model.
- `knowledge/`: educational content rendered by the Learn experience.
- `repository/`: community compatibility metadata and evidence records.
- `schemas/`: versioned data-format definitions once implementation begins.
- `apps/desktop/`: desktop app implementation later.
- `worker/`: Python worker implementation later.
- `packages/`: shared implementation packages later.

No implementation code is included in this scaffold.
