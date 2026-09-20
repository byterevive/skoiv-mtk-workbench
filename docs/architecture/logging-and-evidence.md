# Logging and Evidence

Logs are a first-class subsystem.

## Requirements

- Raw tool output is preserved.
- Parsed/structured events are stored separately.
- Logs are appended to disk during operations rather than only at completion.
- UI rendering is virtualized for large output.
- Users can select, copy, search, filter, save, and export logs.
- The bottom panel can be resized, collapsed, reopened, and should preserve state.
- Individual operations retain separate log histories.
- Important lines can later be pinned as evidence.
- Sanitized sharing exports never overwrite original local logs.
