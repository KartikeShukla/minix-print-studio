# Known Limitations

MiniX Print Studio is still pre-release. The current repository is useful for local
development, mock flows, profile review, and staged hardware certification, but it is
not yet a stable public installer.

## Hardware

- Physical Stage A validation has not been completed in this environment because
  Bluetooth access was unavailable.
- Stage B physical protocol sanity, tiny visual card, and long-print reliability
  runs are pending.
- Printing remains locked until certification stages pass on physical hardware.
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

- The mock print flow is implemented, but real printer transport remains certification-gated.
- Hardware diagnostics artifacts must be reviewed and redacted before public sharing;
  use the Stage A evidence summary for maintainer review before sharing a full ZIP.
- Agent integrations require the desktop app and daemon runtime handoff to be active.

## Security And Privacy

- Do not publish runtime handoff files, bearer tokens, diagnostics containing private
  paths, or unredacted hardware artifacts.
- MCP tools intentionally expose semantic operations only and cannot send raw BLE.
