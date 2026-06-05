# MiniX Print Studio

MiniX Print Studio is an Electron desktop app for designing, previewing, and safely printing thermal notes, receipts, labels, QR cards, and agent-generated snippets on the Seznik MiniX printer profile.

The project is intentionally local-first:

- Electron provides the desktop shell.
- React, Vite, Tailwind, and shadcn-style components provide the renderer.
- A local Python daemon owns BLE, rendering, preview binding, safety checks, and print jobs.
- A stdio MCP shim talks to the daemon rather than directly touching BLE.

## Development

```bash
pnpm install
pnpm test
pnpm dev
```

Python packages live in `daemon/` and `mcp/`.

```bash
.venv/bin/python -m pip install -e daemon -e mcp
```

Stage A hardware validation against a running daemon can be driven from the repo:

```bash
scripts/hardware-test.sh scan
scripts/hardware-test.sh export-read-only --device-id <device-id> --output-dir ./hardware-artifacts
```

## Status

This repository is being built from the implementation plan in `docs/Initial Spec.md`.
