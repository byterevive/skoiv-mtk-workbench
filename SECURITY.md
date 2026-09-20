# Security Policy

Please report security issues privately to the Skoiv Labs maintainers rather than opening a public issue when disclosure could put users or devices at risk.

## Security design goals

- Custom command templates must not become arbitrary host-shell execution.
- External/community metadata is untrusted until validated.
- Logs and diagnostic exports may contain sensitive device or host information.
- Sanitized export must never replace the original local evidence.
- Artifact hashes should be used when redistribution of proprietary firmware is inappropriate.
