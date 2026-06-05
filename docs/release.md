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
pnpm build:sidecars --target-platform <platform>
node scripts/run_python.mjs scripts/write_release_checksums.py dist/release
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

Use `darwin` on macOS and `win32` on Windows. PyInstaller does not
cross-compile, so sidecar builds must run on the same operating system as the
package target.

The release package workflow at `.github/workflows/release-package.yml` runs
unsigned package smokes on native macOS and Windows runners. Use that workflow to
validate Windows sidecar binaries and package inclusion before making Windows
release claims. The workflow also writes `dist/release/SHA256SUMS.txt` before
uploading artifacts so downloaded unsigned packages can be checked against a
deterministic SHA-256 manifest. Electron-builder scratch files such as
`builder-debug.yml` and `.icon-*` conversion caches are excluded from both the
checksum manifest and uploaded artifact.

## Packaging Targets

- macOS: unsigned local Electron package via `pnpm package:mac`; signed release
  build and notarization before stable release.
- Windows: unsigned Electron package via `pnpm package:win` on a Windows runner;
  signed installer before stable release.
- Daemon and MCP sidecars: built with PyInstaller into `dist/sidecars` and
  included in the packaged app as `resources/sidecars`; the daemon sidecar
  bundles the public printer profile data it needs at startup.
- Checksums: generated with
  `node scripts/run_python.mjs scripts/write_release_checksums.py dist/release`
  and included beside the uploaded release artifacts as `SHA256SUMS.txt`.

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
