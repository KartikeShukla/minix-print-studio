# Support Matrix

This matrix describes what the current source tree supports and what still needs
physical validation before a stable public release.

## Platforms

| Platform | Status | Notes |
| --- | --- | --- |
| macOS | Development target | Unsigned local Electron package includes target-host daemon and MCP sidecars; signing and notarization are not complete. |
| Windows | Planned build target | Package script builds Windows sidecars on Windows only; Windows-runner validation, installer packaging, and signing are pending. |
| Linux | Developer-only | Not a first supported desktop release target. |

## Printer Profiles

| Profile | Support Level | Printing Status | Required Evidence |
| --- | --- | --- | --- |
| `seznik-minix-s1-lyin48d-gy` | `official` profile data | Printing remains certification-gated | Stage A physical artifact, Stage B protocol sanity, tiny visual card, and long-print reliability before stable support claims. |

## Agent Integrations

| Client | Status | Notes |
| --- | --- | --- |
| Codex | Config generator and installer support | Uses the token-free runtime handoff file. |
| Claude Desktop / Claude Code | Config generator, installer, and MCPB export support | User must install from the desktop app or generated config. |
| OpenCode | Config generator and installer support | Uses managed local config entries with backups. |
| Generic stdio MCP | Config snippet support | Requires a running desktop app and daemon runtime handoff. |

## Certification Stages

| Stage | Status | Artifact |
| --- | --- | --- |
| Stage A: read-only verification | Implemented in daemon, renderer, and CLI | `hardware-test-<timestamp>.zip` |
| Stage A artifact inspection | Implemented offline | `minix-hardware-test inspect-artifact` |
| Stage B preflight | Implemented offline | `minix-hardware-test protocol-sanity-preflight` |
| Stage B physical protocol sanity | Pending hardware run | Future hardware-test artifact |
| Tiny visual test card | Pending | Future hardware-test artifact |
| Long-print reliability | Pending | Future hardware-test artifact |

Do not treat BLE detection or Stage A alone as permission to print.
