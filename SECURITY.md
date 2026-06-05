# Security Policy

MiniX Print Studio controls a physical printer and exposes local agent tools, so security-sensitive defaults are part of the product contract.

## Supported Versions

No public release has been published yet.

## Reporting a Vulnerability

Please open a private security advisory or contact the maintainers before publishing a vulnerability.

## Design Defaults

- Electron renderers run with Node integration disabled, context isolation enabled, sandbox enabled, and a narrow preload API.
- The daemon binds to localhost and requires bearer-token auth.
- MCP tools are semantic and cannot send raw BLE commands.
- Agent direct printing is disabled by default.
- Integration installers must preview changes, create backups, and support revert.
- CodeQL scans JavaScript/TypeScript and Python changes with the `security-extended` query suite.
- CI and release package workflows declare least-privilege GitHub token permissions instead of relying on repository defaults.
