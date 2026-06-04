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

## Exporting The Stage A Artifact

After read-only verification, use `Export read-only artifact` in the Printer panel.
The daemon runs a fresh `/v1/diagnostics/hardware-test` request for the selected
device and returns a `hardware-test-<timestamp>.zip` artifact.

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
