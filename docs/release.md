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
- Stage A evidence summary generated and reviewed before sharing full artifacts.
- Stage B protocol sanity preflight reviewed before physical run, then recorded
  with `record-protocol-sanity`.
- Tiny visual test card confirmed by the user and recorded with
  `record-tiny-visual-card` from the confirmed Stage B artifact.
- Long-print reliability test completed before stable support claims.

Use `darwin` on macOS and `win32` on Windows. PyInstaller does not
cross-compile, so sidecar builds must run on the same operating system as the
package target.

The release package workflow at `.github/workflows/release-package.yml` runs
unsigned package smokes on native macOS and Windows runners, builds an unsigned
Windows installer, and supports manual `workflow_dispatch` runs for release
evidence capture. Use that workflow to validate Windows sidecar binaries,
package inclusion, and installer creation before making Windows release claims.
The uploaded evidence artifacts are named `minix-print-studio-macos-unsigned`,
`minix-print-studio-windows-unsigned`, and
`minix-print-studio-windows-installer-unsigned`.
The workflow also writes `dist/release/SHA256SUMS.txt` before uploading artifacts
so downloaded unsigned packages can be checked against a deterministic SHA-256
manifest. Electron-builder scratch files such as `builder-debug.yml` and
`.icon-*` conversion caches are excluded from both the checksum manifest and
uploaded artifact.

## Release Evidence Capture

After pushing this branch to a GitHub remote, trigger the release package workflow
and download the uploaded artifacts into a local evidence directory:

```bash
gh workflow run release-package.yml --ref <branch>
gh run view <run-id> --json name,event,conclusion,headBranch > release-evidence/workflow-run.json
gh run download <run-id> --dir release-evidence
node scripts/run_python.mjs scripts/validate_release_evidence.py release-evidence
```

The evidence validator requires a successful manual `Release Package` run,
platform-named macOS and Windows unsigned artifact directories, the unsigned
Windows installer artifact, matching `SHA256SUMS.txt` manifests, bundled
daemon/MCP sidecars, and no runtime state, diagnostics, hardware artifacts, or
electron-builder scratch files. The macOS artifact must also include Bluetooth
usage descriptions in `Info.plist` explaining that Bluetooth is used only to
connect to the local MiniX thermal printer.

## Public History Gate

Before making the repository public, verify that the branch history does not expose
private local-host author or committer metadata:

```bash
pnpm public-history-check
```

The default range is `origin/main..HEAD`. Pass an explicit range when auditing a
different branch or a release tag candidate. If the check reports private metadata,
rewrite the still-private branch history with a reviewed plan and use
`--force-with-lease` only for the branch being sanitized.

## Packaging Targets

- macOS: unsigned local Electron package via `pnpm package:mac`; signed release
  build and notarization before stable release.
- Windows: unsigned Electron package via `pnpm package:win` on a Windows runner;
  unsigned NSIS installer via `pnpm package:win-installer` on a Windows runner;
  signing before stable release.
- Daemon and MCP sidecars: built with PyInstaller into `dist/sidecars` and
  included in the packaged app as `resources/sidecars`; the daemon sidecar
  bundles the public printer profile data it needs at startup.
- Checksums: generated with
  `node scripts/run_python.mjs scripts/write_release_checksums.py dist/release`
  and included beside the uploaded release artifacts as `SHA256SUMS.txt`.

Do not publish installers that embed local runtime state, bearer tokens, diagnostic
artifacts, or private file paths.

## Update Channels

The desktop app exposes stable and beta update-channel selection so testers can
state which release lane they are using. Auto-updates remain disabled for unsigned
builds until signed release publishing is configured and validated.

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

## Beta Feedback

Beta builds should point testers to the desktop Support panel. The panel can export a
redacted support bundle and copy a GitHub beta feedback issue draft that includes the
app version, platform, timestamp, and support bundle file name without private paths.
