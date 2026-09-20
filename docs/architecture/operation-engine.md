# Operation Engine

The UI must not call mtkclient directly.

Conceptual path:

```text
UI intent
  -> operation request
  -> validation
  -> risk classification
  -> safety rules
  -> session/audit creation
  -> adapter execution
  -> logs/evidence/progress
  -> result verification
```

In 0.1, the engine only permits read-oriented device operations.
