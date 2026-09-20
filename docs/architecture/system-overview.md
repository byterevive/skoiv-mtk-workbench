# System Overview

```text
Desktop UI (Tauri + React/TypeScript)
        |
        | structured stdio messages
        v
Python Worker
        |
        +-- Operation / Safety orchestration
        +-- Logging / Evidence
        +-- mtkclient Adapter
        +-- Preloader / DA / Firmware parsers
        +-- Backup engine
        |
        v
MediaTek device / local artifacts
```

Version 0.1 keeps device operations read-only.
