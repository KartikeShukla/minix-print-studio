# Support Matrix

This matrix describes what the current source tree supports and what still needs
physical validation before a stable public release.

## Platforms

| Platform | Status                                          | Notes                                                                                                                                                          |
| -------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| macOS    | Development target                              | Unsigned local Electron package includes target-host daemon and MCP sidecars plus Bluetooth usage descriptions; signing and notarization are not complete.     |
| Windows  | Unsigned package and installer workflow support | Release Package workflow builds the unpacked Windows app plus unsigned NSIS installer on Windows runners with bundled daemon/MCP sidecars; signing is pending. |
| Linux    | Developer-only                                  | Not a first supported desktop release target.                                                                                                                  |

## Printer Profiles

| Profile                      | Support Level           | Printing Status                                                                                                                                                                                                                                                                                                                    | Required Evidence                                                                                                                                                                                                    |
| ---------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `seznik-minix-s1-lyin48d-gy` | `official` profile data | Experimental physical transfer, operator-confirmation recording, Stage B/C artifact recording, local trusted-printer record generation/inspection, long-print reliability print/artifact commands, stable-support gate recording, and agent-direct policy-review recording implemented; agent direct printing remains opt-in gated | Stage A/B/C/D physical evidence exists locally; stable support claims and long-print trust require the local stable-support gate record, while agent direct printing requires a later explicit user opt-in workflow. |

## Agent Integrations

| Client                       | Status                                               | Notes                                                       |
| ---------------------------- | ---------------------------------------------------- | ----------------------------------------------------------- |
| Codex                        | Config generator and installer support               | Uses the token-free runtime handoff file.                   |
| Claude Desktop / Claude Code | Config generator, installer, and MCPB export support | User must install from the desktop app or generated config. |
| OpenCode                     | Config generator and installer support               | Uses managed local config entries with backups.             |
| Generic stdio MCP            | Config snippet support                               | Requires a running desktop app and daemon runtime handoff.  |

## Certification Stages

| Stage                                  | Status                                                                                                                                                                                | Artifact                                                                                                          |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Host Bluetooth readiness               | Implemented for macOS CLI and Electron diagnostics, with guarded Stage A CLI options                                                                                                  | `minix-hardware-test host-readiness` / `scan --require-host-ready` / Printer panel                                |
| Stage A: read-only verification        | Implemented in daemon, renderer, and CLI; physically verified on 2026-06-06 for `Seznik MiniX_0194_LE`                                                                                | `hardware-test-<timestamp>.zip`                                                                                   |
| Stage A artifact inspection            | Implemented offline                                                                                                                                                                   | `minix-hardware-test inspect-artifact`                                                                            |
| Stage A shareable evidence summary     | Implemented offline and shown in Electron artifact inspection                                                                                                                         | `minix-hardware-test evidence-summary`                                                                            |
| Stage B preflight                      | Implemented offline                                                                                                                                                                   | `minix-hardware-test protocol-sanity-preflight`                                                                   |
| Stage B physical protocol sanity       | Artifact recording implemented; local reviewed artifact recorded on 2026-06-06                                                                                                        | `minix-hardware-test record-protocol-sanity`                                                                      |
| Stage C tiny visual card preflight     | Implemented offline                                                                                                                                                                   | `minix-hardware-test tiny-visual-card-preflight`                                                                  |
| Stage C physical tiny visual test card | Artifact recording implemented; local reviewed artifact recorded on 2026-06-06 from a confirmed daemon job                                                                            | `minix-hardware-test record-tiny-visual-card`                                                                     |
| Trusted printer record                 | Implemented and surfaced in the desktop Printer setup flow for manual continuous printing only; keeps long-print, stable support, and agent direct printing disabled                  | `minix-hardware-test record-trusted-printer`, `minix-hardware-test inspect-trusted-printer-record`                |
| Long-print reliability                 | Print execution, operator confirmation, and artifact recording completed locally on 2026-06-06                                                                                        | `minix-hardware-test print-long-print-reliability`, then `minix-hardware-test record-long-print-reliability`      |
| Stable support gate                    | Implemented as an offline local record from reviewed Stage A/B/C/trusted-record/Stage D evidence and surfaced in the desktop Printer setup flow; keeps agent direct printing disabled | `minix-hardware-test record-stable-support-gate`, `minix-hardware-test inspect-stable-support-gate`               |
| Agent-direct policy review             | Implemented as an offline local record from the stable-support gate and surfaced in the desktop Printer setup flow; keeps direct printing disabled pending explicit user opt-in       | `minix-hardware-test record-agent-direct-policy-review`, `minix-hardware-test inspect-agent-direct-policy-review` |

Do not treat BLE detection, Stage A, or an unverified transfer alone as stable
printer certification.
