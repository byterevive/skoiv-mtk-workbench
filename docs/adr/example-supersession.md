# ADR Supersession Example

This is an example only; it is not an active architectural decision.

Suppose ADR-0005 originally says:

```text
Status: Accepted
Decision: Use JSON messages over stdio.
```

Later the project adopts a different IPC protocol in ADR-0042.

Update ADR-0005 to:

```text
Status: Superseded by ADR-0042
Superseded by: ADR-0042
```

ADR-0042 should contain:

```text
Status: Accepted
Supersedes: ADR-0005
```

If the old decision is simply retired and there is no direct replacement, mark it `Deprecated` instead.

Never delete ADR-0005 and never rewrite its original context/decision to match ADR-0042.
