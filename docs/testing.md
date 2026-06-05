# Testing

Development follows TDD for behavior code.

## Local Gates

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

## Test Layers

- Unit tests for schema validation, profile matching, config generation, protocol commands, raster packing, safety metrics, and print planning.
- Golden tests for canonical rendering and packed raster outputs.
- Mock BLE tests for scan, connect, flow control, disconnects, missing final OK, and partial-output states.
- Hardware tests are explicit and separate from CI. Stage A exports a read-only
  `hardware-test-<timestamp>.zip` artifact and must not unlock printing.
- Host-readiness tests cover the CLI diagnostic that distinguishes local
  Bluetooth controller visibility failures from printer-level Stage A failures.
- Desktop and renderer tests cover exposing that host-readiness result in the
  Printer panel before Stage A scan attempts.
- Offline certification-preflight tests cover Stage B protocol command metadata
  and Stage C tiny-card metadata without sending BLE writes or including printable
  raster bytes.
- Desktop support bundle tests cover redacted log/crash ZIP export and the renderer
  support action without requiring hardware.
- Renderer setup tests cover the first-run checklist and local dismissal persistence.
- UI E2E tests cover onboarding, mock print flow, preview, safety warnings, and integration setup.

## Release Evidence Gate

After a manual Release Package workflow run, download the uploaded artifacts and run:

```bash
node scripts/run_python.mjs scripts/validate_release_evidence.py release-evidence
```

This validates the successful workflow metadata, macOS and Windows unsigned package
artifacts, checksum manifests, bundled sidecars, and forbidden artifact exclusions.
The current release evidence baseline is Release Package workflow run `27013383603`.

## Dependency Maintenance

Dependabot opens weekly update pull requests for the npm workspace, GitHub Actions,
and the Python daemon/MCP packages. These updates must still pass the local gates
above before merge.

## Static Analysis

CodeQL runs in GitHub Actions for JavaScript/TypeScript and Python on pull
requests, pushes to `main`, weekly schedule, and manual dispatch. Local validation
keeps the workflow present, configured for the `security-extended` query suite,
and limited to `actions: read`, `contents: read`, and `security-events: write`
so GitHub can read workflow-run metadata and receive scan results. CI and
release package workflows must keep explicit
read-only `contents` permissions unless a future release step documents and
validates a narrower write requirement. Required workflows also opt into the
Node 24 JavaScript action runtime so GitHub Actions runtime migrations are
exercised before they become the default.

While the repository remains private, the CodeQL job skips by default because code
scanning is not enabled on this private repo. Set repository variable
`MINIX_ENABLE_PRIVATE_CODEQL=true` after enabling private code scanning, or make
the repository public, to run CodeQL.
