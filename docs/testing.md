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
- Safety tests cover profile-backed thermal coverage thresholds, daemon
  recomputation for raw raster previews, blocked-preview rejection before
  plan/print execution, and renderer display of blocked preview details while
  Print stays disabled.
- Print planning tests cover profile-backed thermal pacing metadata for each
  band, including black-dot coverage and cooldown delays exposed without raw
  raster bytes.
- Golden tests for canonical rendering and packed raster outputs.
- Mock BLE tests for scan, connect, flow control, disconnects, missing final OK, and partial-output states.
- Mock print-queue tests cover segment-boundary transport disconnects so printable
  partial output is never reported as a safe retry or verified completion.
- Physical-transport unit tests cover AiYin/LuckPrinter command sequencing,
  profile chunking, name-only advertisement scan fallback, and explicit
  `deviceId` targeting before non-mock output.
- Hardware tests are explicit and separate from CI. Stage A exports a read-only
  `hardware-test-<timestamp>.zip` artifact and must not unlock printing.
- Host-readiness tests cover the CLI diagnostic that distinguishes local
  Bluetooth controller visibility failures from printer-level Stage A failures
  and emits remediation actions for blocked hosts.
- Guarded Stage A CLI tests cover `scan --require-host-ready` and
  `export-read-only --require-host-ready` refusing daemon contact when host
  Bluetooth readiness blocks Stage A.
- Desktop and renderer tests cover exposing that host-readiness result in the
  Printer panel before Stage A scan attempts, including recommended actions.
- Offline certification-preflight tests cover Stage B protocol command metadata
  and Stage C tiny-card metadata without sending BLE writes or including printable
  raster bytes.
- Offline evidence-summary tests cover maintainer-shareable Stage A summaries
  with hashed device fingerprints and explicit omission of artifact paths, raw
  logs, command hex payloads, bearer tokens, and raster bytes.
- MCP tool tests cover approval-required print-note policy decisions, safety
  metric propagation, approval-token redaction, spec-facing `render_preview`,
  and redacted job-status lookup through the stdio server.
- MCP profile-list tests cover supported-profile summaries that omit BLE UUIDs,
  read-only probe commands, and protocol payload details while keeping profile
  dimensions and agent safety limits available.
- Operator confirmation tests cover daemon job state transition, HTTP
  confirmation recording, diagnostics inclusion, renderer daemon-client calls,
  and the print-status confirmation action.
- Desktop support bundle tests cover redacted log/crash ZIP export and the renderer
  support action without requiring hardware.
- Renderer setup tests cover the first-run checklist and local dismissal persistence.
- UI E2E tests cover onboarding, mock print flow, preview, safety warnings, and integration setup.

## Physical Validation Notes

Physical validation is not part of CI. On 2026-06-06, an unsandboxed non-mock
daemon on `127.0.0.1:39282` completed:

- `scripts/hardware-test.sh --timeout 25 scan --require-host-ready`
- `scripts/hardware-test.sh --timeout 45 export-read-only --device-id <device-id>
  --require-host-ready --output-dir <local-output-dir>`
- Offline `inspect-artifact`, `protocol-sanity-preflight`,
  `tiny-visual-card-preflight`, and `evidence-summary`
- One experimental tiny-card `/v1/jobs/print` transfer that reported
  `completed_unverified`; operator paper-output confirmation recording is
  implemented, but reviewed Stage C artifact evidence remains required.

## Release Evidence Gate

After a manual Release Package workflow run, download the uploaded artifacts and run:

```bash
node scripts/run_python.mjs scripts/validate_release_evidence.py release-evidence
```

This validates the successful workflow metadata, macOS and Windows unsigned package
artifacts, the unsigned Windows installer artifact, checksum manifests, bundled
sidecars, and forbidden artifact exclusions. The macOS artifact must include
Bluetooth usage descriptions in `Info.plist` so first-run permission prompts
explain local printer access. The current pre-installer release evidence
baseline is Release Package workflow run `27053365446`; newer Windows installer
evidence must include `minix-print-studio-windows-installer-unsigned`.

## Public History Gate

Before switching the repository from private to public, run:

```bash
pnpm public-history-check
```

This checks the `origin/main..HEAD` commit range for private local-host author and
committer metadata. It is a pre-public gate, not a hardware gate.

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

On the public repository, CodeQL runs on pull requests, pushes to `main`, weekly
schedule, and manual dispatch. If the repository is temporarily made private
again, CodeQL skips by default unless repository variable
`MINIX_ENABLE_PRIVATE_CODEQL=true` is set after enabling private code scanning.
