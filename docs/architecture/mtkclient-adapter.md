# mtkclient Adapter

The adapter is the only layer that understands how Workbench operations map to mtkclient behavior.

The UI, backup engine, firmware inspector, and safety layer should depend on Workbench operation contracts rather than direct mtkclient internals.
