# Backup Engine

Selective BROM backup is part of the 0.1 foundation.

Conceptual workflow:

```text
Detect device
 -> read GPT
 -> user selects partitions/preset
 -> review read-only plan
 -> stream partition data to disk
 -> compute SHA-256
 -> validate expected sizes
 -> generate versioned manifest
 -> show verification result
```

Partition presets are advisory and device-aware; they must not assume every MediaTek device uses identical partition names.
