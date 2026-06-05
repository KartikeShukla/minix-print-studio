# Hardware Certification

Hardware certification is explicit and staged. A printer can be detected and read-only
verified without being safe to print.

## Stage A: Read-Only Verification

Stage A checks identity and BLE shape only:

- Scan for the printer.
- Connect to the selected device.
- Discover services and characteristics.
- Subscribe to notify characteristics.
- Query model and firmware from the known profile commands.
- Export the hardware-test artifact.

Stage A must not move paper, send raster bytes, or unlock printing.

If the host cannot access Bluetooth, the scan/export flow returns a structured
hardware error such as:

```json
{
  "detail": "Bluetooth unavailable: Bluetooth is unsupported"
}
```

Resolve Bluetooth availability, OS permission, or host adapter setup before treating
Stage A as attempted.

## Exporting The Stage A Artifact

After read-only verification, use `Export read-only artifact` in the Printer panel.
The daemon runs a fresh `/v1/diagnostics/hardware-test` request for the selected
device and returns a `hardware-test-<timestamp>.zip` artifact.

Use `Inspect Stage A artifact` in the Printer panel to select an exported artifact,
run the same offline safety inspection used by the CLI, and review the Stage B
protocol sanity preflight without sending BLE writes.

For command-line validation against a running daemon:

```bash
scripts/hardware-test.sh scan
scripts/hardware-test.sh export-read-only --device-id <device-id> --output-dir ./hardware-artifacts
scripts/hardware-test.sh inspect-artifact ./hardware-artifacts/hardware-test-<timestamp>.zip
scripts/hardware-test.sh protocol-sanity-preflight ./hardware-artifacts/hardware-test-<timestamp>.zip
```

The wrapper uses `.venv/bin/python` when available and accepts
`MINIX_DAEMON_BASE_URL`, `MINIX_DAEMON_TOKEN`, and `MINIX_PYTHON` overrides.
`inspect-artifact` runs offline, checks the required archive files, and rejects
artifacts that sent print commands, included raster bytes, unlocked printing, or
marked certification complete.
`protocol-sanity-preflight` also runs offline. It validates the Stage A artifact
and prints the exact Stage B wake, density, and paper-mode command bytes from the
captured profile snapshot, without sending anything over BLE.

The Stage A archive contains:

- `device.json`
- `profile.json`
- `ble-discovery.json`
- `model-response.bin`
- `firmware-response.bin`
- `notifications.log`
- `commands.log`
- `print-transfer-manifest.json`
- `band-manifest.json`
- `finalizer-result.json`
- `safety-report.json`
- `user-confirmation.json`
- `app-version.json`
- `README.md`

For Stage A, `print-transfer-manifest.json` must report:

```json
{
  "stage": "read_only_verification",
  "printCommandsSent": false,
  "rasterBytesIncluded": false
}
```

`safety-report.json` must keep `printingLocked` set to `true` and
`certificationComplete` set to `false`.

## Certification Boundary

The Stage A artifact is a validation record, not printer certification. Printing remains
locked until later stages pass on physical hardware:

1. Protocol sanity test.
2. Tiny visual test card.
3. Long-print reliability test.
4. Optional paper mode tests.

Do not mark a profile as trusted from read-only verification alone.

## Stage B Preflight

Before a physical protocol sanity run, review the offline preflight output:

- Confirm `stage` is `protocol_sanity_test`.
- Confirm `printCommandsSent` is `false`.
- Confirm `rasterBytesIncluded` is `false`.
- Confirm the command list contains only `wake`, `set_density`, and
  `set_paper_mode`.

The preflight output is not a certification result. It is the deterministic
command plan for the next physical test.

## Long-Print Test Fixture

The renderer toolbar includes `Insert long-print test markers` for preparing a
deterministic continuous-paper fixture before later physical reliability tests.
The command extends the document to 8000 dots and inserts visible
`START LP-TEST`, 25%, 50%, 75%, and `END LP-TEST checksum: 7F3A` markers.

This fixture helps compare the preview, band plan, and physical output. It does
not unlock trusted printing or replace the Stage B, tiny visual card, or
long-print reliability hardware runs.
