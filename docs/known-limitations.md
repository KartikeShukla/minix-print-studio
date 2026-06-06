# Known Limitations

MiniX Print Studio is still pre-release. The current repository is useful for local
development, mock flows, profile review, and staged hardware certification, but it is
not yet a stable public installer.

## Hardware

- Physical Stage A validation completed on 2026-06-06 for
  `Seznik MiniX_0194_LE`: model `S1_LYiN48D_GY`, firmware `V1.9.11`, and a
  read-only artifact inspected as safe.
- macOS advertisements for this unit may omit service UUIDs, so discovery must
  fall back from FF00-filtered scanning to name-prefix matching before read-only
  verification.
- Stage B physical protocol sanity and Stage C tiny-card artifact evidence exists
  locally. Long-print reliability artifact recording is implemented, but a
  reviewed physical long-print reliability artifact is still pending.
- User-initiated physical BLE transfer is implemented as an experimental path,
  and operator paper-output confirmation can now be recorded on the job. Stage
  B/C artifact-recording, local trusted-printer record, and long-print
  reliability artifact commands are implemented, but stable support still
  requires reviewed physical long-print reliability evidence.
- Only the Seznik MiniX profile is present.

## Packaging

- Daemon and MCP sidecar binary production and package inclusion are implemented
  for target-host builds.
- Windows sidecar package validation must run on a Windows runner because
  PyInstaller does not cross-compile; the Release Package workflow runs Windows
  package and installer validation on Windows runners.
- macOS signing and notarization are not configured.
- Windows installer packaging is implemented for unsigned NSIS artifacts, but
  signing is not configured.
- Linux is not a supported first release target.

## Product Surface

- The mock print flow, experimental physical BLE transport, and manual continuous
  trusted-printer record path are implemented. Long-print reliability artifact
  recording exists, but long-print and agent-direct trust remain
  certification-gated until reviewed physical evidence exists.
- Hardware diagnostics artifacts must be reviewed and redacted before public sharing;
  use the Stage A evidence summary for maintainer review before sharing a full ZIP.
- Agent integrations require the desktop app and daemon runtime handoff to be active.

## Security And Privacy

- Do not publish runtime handoff files, bearer tokens, diagnostics containing private
  paths, or unredacted hardware artifacts.
- MCP tools intentionally expose semantic operations only and cannot send raw BLE.
