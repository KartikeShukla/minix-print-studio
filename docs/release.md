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

- macOS: Electron package, signed release build, notarization before stable release.
- Windows: Electron package, signed installer before stable release.

Do not publish installers that embed local runtime state, bearer tokens, diagnostic
artifacts, or private file paths.

## Release Notes

Release notes should include:

- Supported printer profiles and certification stage.
- Known limitations from [known-limitations.md](known-limitations.md).
- Support status from [support-matrix.md](support-matrix.md).
- Upgrade and uninstall notes.
- Diagnostics redaction statement.
- Hardware validation evidence summary.
