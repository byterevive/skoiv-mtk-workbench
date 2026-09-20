# IPC Protocol — Design Notes

The desktop app and Python worker communicate using structured JSON messages over stdio.

The eventual protocol should distinguish at minimum:

- request
- response
- operation-started
- progress
- structured-log-event
- raw-output
- evidence
- warning/problem
- operation-completed
- operation-failed
- cancellation
- worker-health

The protocol must be versioned before it becomes a stable public contract.
