# MiniX Print Studio

MiniX Print Studio is a local-first Electron desktop app for designing, previewing,
and safely printing thermal notes, receipts, labels, QR cards, and agent-generated
snippets for the Seznik MiniX printer profile.

The app is built around a strict separation of concerns:

- Electron provides the desktop shell and installer-facing integrations.
- React, Vite, Tailwind, and shadcn-style components provide the editor UI.
- A local Python daemon owns BLE, rendering, preview binding, safety checks, and
  print jobs.
- A stdio MCP shim talks to the daemon instead of touching BLE directly.

## Project Status

This repository is being built from the implementation plan in
[docs/Initial Spec.md](docs/Initial%20Spec.md). It is still pre-release: no stable
public release has been published, and physical printer certification is not complete.

The current development branch has mock printing, document editing, daemon-backed
preview and planning, MCP integration scaffolding, unsigned macOS and Windows
package evidence, and community governance docs. Printing to hardware remains gated
until the staged certification flow produces reviewed evidence.

## Safety Model

MiniX Print Studio controls a physical printer, so safety defaults are part of the
product contract:

- The daemon is the only layer that owns printer protocol and BLE access.
- MCP tools are semantic and cannot send raw BLE commands.
- Preview and print planning use daemon-generated approval artifacts.
- Agent direct printing is disabled by default.
- Hardware tests are explicit, separate from CI, and must not unlock printing by
  detection alone.
- Support bundles, diagnostics, and hardware evidence must be redacted before
  sharing.

See [docs/safety.md](docs/safety.md) and [SECURITY.md](SECURITY.md) for the full
contract.

## Supported Printers

The first profile target is `seznik-minix-s1-lyin48d-gy`. The profile data is tracked
in the repository, but stable support still requires physical evidence:

- Stage A read-only identity and BLE-shape verification.
- Stage B physical protocol sanity after the offline preflight passes.
- Stage C tiny visual test card confirmation.
- Long-print reliability before stable support claims.

Do not treat BLE discovery, a matching name, or a matching service UUID as permission
to print. See [docs/support-matrix.md](docs/support-matrix.md) and
[docs/printer-profiles.md](docs/printer-profiles.md).

## Development

Install JavaScript dependencies:

```bash
pnpm install
```

Install Python packages into the repo virtual environment:

```bash
.venv/bin/python -m pip install -e daemon[dev] -e mcp[dev]
```

Run the desktop app during development:

```bash
pnpm dev
```

Run the normal non-hardware gates before proposing a change:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm open-source-check
pnpm source-package-check
pnpm release-package-check
.venv/bin/python -m ruff check daemon mcp
.venv/bin/python -m mypy daemon/src mcp/src
.venv/bin/python -m pytest daemon/tests mcp/tests
```

Development follows TDD for behavior changes. Write the failing test first, make it
pass with the smallest scoped change, then refactor while keeping the suite green.

## Hardware Certification

Stage A hardware validation against a running daemon can be driven from the repo.
Start with host Bluetooth readiness:

```bash
scripts/hardware-test.sh host-readiness
```

Only continue if the readiness output reports that Stage A can scan from the current
host context:

```bash
scripts/hardware-test.sh scan
scripts/hardware-test.sh export-read-only --device-id <device-id> --output-dir ./hardware-artifacts
scripts/hardware-test.sh inspect-artifact ./hardware-artifacts/hardware-test-<timestamp>.zip
scripts/hardware-test.sh protocol-sanity-preflight ./hardware-artifacts/hardware-test-<timestamp>.zip
scripts/hardware-test.sh tiny-visual-card-preflight ./hardware-artifacts/hardware-test-<timestamp>.zip
scripts/hardware-test.sh evidence-summary ./hardware-artifacts/hardware-test-<timestamp>.zip
```

Stage A artifacts are validation records, not certification. Prefer the redacted
evidence summary for maintainer review before sharing full ZIP artifacts. The physical
Stage B and Stage C executors stay locked until Stage A evidence is reviewed.

See [docs/hardware-certification.md](docs/hardware-certification.md) and
[docs/troubleshooting.md](docs/troubleshooting.md).

## Agent Integrations

MiniX Print Studio exposes a local MCP integration path for Codex, Claude Desktop,
Claude Code, OpenCode, and generic stdio MCP clients. The desktop app generates
token-free config snippets and uses a runtime handoff file so clients can discover the
local daemon without embedding bearer tokens.

The MCP server can preview documents and notes through daemon approval flows. It does
not bypass preview approval, unlock trusted printing, or expose raw BLE access.

See [docs/mcp-integrations.md](docs/mcp-integrations.md).

## Release and Validation

Release work is evidence-driven. Unsigned package validation is currently available
for macOS and Windows, while signing, notarization, installer publishing, and stable
hardware support remain pending.

Use the release docs for package evidence capture:

- [docs/release.md](docs/release.md)
- [docs/release-notes-template.md](docs/release-notes-template.md)
- [docs/testing.md](docs/testing.md)
- [docs/known-limitations.md](docs/known-limitations.md)

The repository stays private during pre-publication validation. Before public release,
the branch needs passing non-hardware gates, reviewed release package evidence, and the
hardware certification evidence described above. Run `pnpm public-history-check`
before making the repository public so branch history does not expose private
local-host author or committer metadata.
