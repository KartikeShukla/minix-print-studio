# Release

This project has not published a stable public release yet. Release work should stay
evidence-driven and separate from normal development commits.

## Pre-Release Gates

Run the non-hardware gates:

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
python3 scripts/validate_open_source_readiness.py
```

Hardware gates are separate from CI and require the physical printer:

- Stage A read-only verification artifact exported and inspected.
- Stage B protocol sanity preflight reviewed before physical run.
- Tiny visual test card confirmed by the user.
- Long-print reliability test completed before stable support claims.

## Packaging Targets

- macOS: unsigned local Electron package scaffold via `pnpm package:mac`; signed
  release build and notarization before stable release.
- Windows: unsigned local Electron package scaffold via `pnpm package:win`; signed
  installer before stable release.
- Daemon and MCP sidecars: packaged app path resolution targets
  `resources/sidecars`; PyInstaller sidecar binary production is still required
  before publishing installers.

Do not publish installers that embed local runtime state, bearer tokens, diagnostic
artifacts, or private file paths.

## Release Notes

Use [release-notes-template.md](release-notes-template.md) as the starting point
for every public release note.

Release notes should include:

- Supported printer profiles and certification stage.
- Known limitations from [known-limitations.md](known-limitations.md).
- Support status from [support-matrix.md](support-matrix.md).
- Upgrade and uninstall notes.
- Diagnostics redaction statement.
- Hardware validation evidence summary.
