# Hardware Certification

Hardware certification is explicit and staged. A printer can be detected and read-only
verified without being safe to print.

## Stage A: Read-Only Verification

Stage A checks identity and BLE shape only:

- Check host Bluetooth readiness.
- Scan for the printer.
- Connect to the selected device.
- Discover services and characteristics.
- Subscribe to notify characteristics.
- Query model and firmware from the known profile commands.
- Export the hardware-test artifact.

Stage A must not move paper, send raster bytes, or unlock printing.

On macOS, the Seznik MiniX may advertise its local name without advertising the
FF00 service UUID. The daemon therefore tries the profile service filter first,
then falls back to an unfiltered scan and classifies known name-prefix matches as
`detected_unverified`. Read-only verification must still connect and confirm the
model/firmware before the artifact can advance to protocol sanity.

If the host cannot access Bluetooth, the scan/export flow returns a structured
hardware error such as:

```json
{
  "detail": "Bluetooth unavailable: Bluetooth is unsupported"
}
```

Resolve Bluetooth availability, OS permission, or host adapter setup before treating
Stage A as attempted.

Before scanning, use `Check host Bluetooth` in the Printer panel or run:

```bash
scripts/hardware-test.sh host-readiness
```

On macOS, this checks whether `system_profiler SPBluetoothDataType` exposes a
Bluetooth controller to the current process. A `not_visible` result means Stage A
cannot start from that host context yet. The CLI JSON and Printer panel include
`recommendedActions` for Bluetooth settings, unsandboxed execution, and adapter
restart checks before retrying `scan`.

## Exporting The Stage A Artifact

After read-only verification, use `Export read-only artifact` in the Printer panel.
The daemon runs a fresh `/v1/diagnostics/hardware-test` request for the selected
device and returns a `hardware-test-<timestamp>.zip` artifact.

Use `Inspect Stage A artifact` in the Printer panel to select an exported artifact,
run the same offline safety inspection used by the CLI, and review the Stage B
protocol sanity and Stage C tiny visual card preflights without sending BLE
writes.

For command-line validation against a running daemon:

```bash
scripts/hardware-test.sh --base-url http://127.0.0.1:39282 scan --require-host-ready
scripts/hardware-test.sh --base-url http://127.0.0.1:39282 export-read-only --device-id <device-id> --require-host-ready --output-dir ./hardware-artifacts
scripts/hardware-test.sh inspect-artifact ./hardware-artifacts/hardware-test-<timestamp>.zip
scripts/hardware-test.sh protocol-sanity-preflight ./hardware-artifacts/hardware-test-<timestamp>.zip
scripts/hardware-test.sh tiny-visual-card-preflight ./hardware-artifacts/hardware-test-<timestamp>.zip
scripts/hardware-test.sh evidence-summary ./hardware-artifacts/hardware-test-<timestamp>.zip
```

The wrapper uses `.venv/bin/python` when available and accepts
`MINIX_DAEMON_BASE_URL`, `MINIX_DAEMON_TOKEN`, and `MINIX_PYTHON` overrides.
Prefer `--base-url` for guarded Stage A runs against a non-default daemon port;
on macOS, environment overrides can affect the subprocess context used by the
local Bluetooth readiness probe before daemon contact.
Use `--require-host-ready` for hardware Stage A runs so `scan` and
`export-read-only` refuse daemon contact when the current host cannot expose a
Bluetooth controller. Development-only mock scans may omit the guard.
`inspect-artifact` runs offline, checks the required archive files, and rejects
artifacts that sent print commands, included raster bytes, unlocked printing, or
marked certification complete.
`protocol-sanity-preflight` also runs offline. It validates the Stage A artifact
and prints the exact Stage B wake, density, and paper-mode command bytes from the
captured profile snapshot, without sending anything over BLE.
`tiny-visual-card-preflight` runs offline as well. It validates the same Stage A
artifact and emits deterministic Stage C card metadata for `MINIX TEST 7K4P`,
including width, height, raster byte counts, and a SHA-256 digest. It does not
include printable raster bytes and does not replace the required physical Stage B
pass or user confirmation.
`evidence-summary` builds a maintainer-shareable summary from the same offline
checks. It includes the profile id, next required stage, redacted device
fingerprint, preflight counts, tiny-card digest, and explicit redaction flags,
but omits the artifact path, raw logs, command hex payloads, raster bytes, bearer
tokens, and the raw device id.

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

After a reviewed physical Stage B run, record the operator result as a hardware
artifact:

```bash
scripts/hardware-test.sh record-protocol-sanity \
  --stage-a-artifact <stage-a.zip> \
  --confirmed-at <utc-timestamp> \
  --operator-note "<what happened on paper and device LEDs>" \
  --no-paper-moved \
  --no-error \
  --output-dir <local-output-dir>
```

This writes `hardware-test-protocol-sanity.zip`. The artifact records the command
plan, operator confirmation, and safety report, but does not include raster bytes
and does not unlock trusted printing.

## Stage C Preflight

After Stage A inspection, review the tiny visual card preflight before adding any
physical card-print executor:

- Confirm `stage` is `tiny_visual_test_card`.
- Confirm `requiredPriorStage` is `protocol_sanity_test`.
- Confirm `displayText` is `MINIX TEST 7K4P`.
- Confirm `heightDots` is between 120 and 180.
- Confirm `printCommandsSent` is `false`.
- Confirm `rasterBytesIncluded` is `false`.
- Confirm `safety.preflightOnly` is `true`.

The physical Stage C run must still wait for a passed Stage B protocol sanity run.
When the tiny card is eventually printed, the operator must confirm the text is
readable, left/right edge markers are visible, output is not mirrored or upside
down, and feed completes without stall, overheat warning, disconnect, or fatal
error.

The daemon may report a physical tiny-card transfer as `completed_unverified`
after all BLE bands are written. That is not certification. It only means the
transport finished from the daemon's perspective; a human must inspect the paper
output and record the confirmation before treating the stage as passed. The app
and daemon can record this confirmation on the print job, but Stage C still needs
a reviewed hardware-test artifact before the profile becomes trusted.

After Stage B has a confirmed artifact and the tiny-card print job has operator
paper-output confirmation recorded on the daemon job, record the Stage C artifact:

```bash
scripts/hardware-test.sh record-tiny-visual-card \
  --stage-a-artifact <stage-a.zip> \
  --protocol-sanity-artifact <hardware-test-protocol-sanity.zip> \
  --job-id <confirmed-job-id> \
  --output-dir <local-output-dir>
```

This writes `hardware-test-tiny-visual-card-<job-id>.zip`. The command verifies
the confirmed Stage B artifact, verifies the daemon job is
`confirmed_complete`, stores a SHA-256 digest of the Stage B artifact, and keeps
`printingLocked` true. It still does not complete certification; long-print
reliability remains required before stable support claims.

## Trusted Printer Record

After Stage A, Stage B, and Stage C artifacts have been reviewed, record the
local trust decision:

```bash
scripts/hardware-test.sh record-trusted-printer \
  --stage-a-artifact <stage-a.zip> \
  --protocol-sanity-artifact <hardware-test-protocol-sanity.zip> \
  --tiny-visual-card-artifact <hardware-test-tiny-visual-card-job-id.zip> \
  --output-dir <local-output-dir>
```

This writes `trusted-printer-<device-fingerprint>.json`. The record enables only
`manual_continuous_printing`, stores a redacted device fingerprint plus SHA-256
digests for the Stage A/B/C evidence chain, and keeps long-print, stable support
claims, and agent direct printing disabled until long-print reliability passes.
Inspect the record before sharing or relying on it:

```bash
scripts/hardware-test.sh inspect-trusted-printer-record <trusted-printer-device-fingerprint.json>
```

The CLI inspection runs offline and prints only a status line to stdout. It
rejects records that expose a raw device id, include operator free text, skip
long-print reliability, or enable long-print trust, stable support claims, or
agent direct printing. In the desktop app, use `Inspect trusted-printer record`
in the Printer panel to validate the selected JSON through the same CLI path and
show the redacted manual-continuous trust state in the setup flow.

## Stage D Long-Print Reliability Artifact

After Stage A/B/C artifacts have been reviewed, the printer has a trusted-printer
record, and the printer is powered on nearby, print the deterministic long-print
marker fixture through the daemon:

```bash
scripts/hardware-test.sh print-long-print-reliability \
  --stage-a-artifact <stage-a.zip> \
  --protocol-sanity-artifact <hardware-test-protocol-sanity.zip> \
  --tiny-visual-card-artifact <hardware-test-tiny-visual-card-job-id.zip> \
  --trusted-printer-record <trusted-printer-device-fingerprint.json>
```

This command validates the Stage A/B/C/trusted-record chain, generates an
8000-dot low-coverage marker strip with START, 25%, 50%, 75%, and END markers,
creates a daemon preview, and submits the physical print job. Stdout is
status-only to avoid leaking local identifiers or daemon approval tokens. Use the
desktop print status or `/v1/jobs` to read the confirmed daemon job id for the
recording command. The CLI uses a 10-minute timeout for the physical print
request and still requires operator paper-output confirmation.

After the output is reviewed and the daemon job has operator paper-output
confirmation recorded, record the Stage D artifact:

```bash
scripts/hardware-test.sh record-long-print-reliability \
  --stage-a-artifact <stage-a.zip> \
  --protocol-sanity-artifact <hardware-test-protocol-sanity.zip> \
  --tiny-visual-card-artifact <hardware-test-tiny-visual-card-job-id.zip> \
  --trusted-printer-record <trusted-printer-device-fingerprint.json> \
  --job-id <confirmed-long-print-job-id> \
  --output-dir <local-output-dir>
```

This writes `hardware-test-long-print-reliability-<job-id>.zip`. The command
validates the Stage A/B/C/trusted-record chain, verifies the daemon job is a
confirmed long-print transfer with all planned bands, rows, bytes, and protected
tail rows sent, stores only redacted device identity, and omits raster bytes and
operator free text. The artifact records that the long-print run passed, but it
does not by itself enable stable support claims or agent direct printing.

## Stable Support Gate Record

After maintainers review the Stage D artifact, record the local stable-support
gate:

```bash
scripts/hardware-test.sh record-stable-support-gate \
  --stage-a-artifact <stage-a.zip> \
  --protocol-sanity-artifact <hardware-test-protocol-sanity.zip> \
  --tiny-visual-card-artifact <hardware-test-tiny-visual-card-job-id.zip> \
  --trusted-printer-record <trusted-printer-device-fingerprint.json> \
  --long-print-reliability-artifact <hardware-test-long-print-reliability-job-id.zip> \
  --output-dir <local-output-dir>
```

This writes `stable-support-gate-<device-fingerprint>.json`. The command runs
offline, validates the full Stage A/B/C/trusted-record/Stage D evidence chain,
keeps stdout status-only, stores only a redacted device fingerprint and artifact
digests, and omits raster bytes plus operator free text. The gate enables manual
continuous printing, long-print continuous printing, and stable support claims.
It keeps `agentDirectPrintingEnabled: false` and records the next required stage
as `agent_direct_printing_policy_review`.

Inspect the gate before relying on it:

```bash
scripts/hardware-test.sh inspect-stable-support-gate <stable-support-gate-device-fingerprint.json>
```

The CLI inspection runs offline and prints only a status line to stdout. It
rejects records that expose a raw device id, include operator free text or raster
bytes, omit the Stage A/B/C/trusted-record/Stage D evidence digests, or enable
agent direct printing. In the desktop app, use `Inspect stable-support gate` in
the Printer panel to validate the selected JSON through the same CLI path and
show the reviewed Stage D state in the setup flow.

Record the agent-direct policy-review gate from the stable-support gate:

```bash
scripts/hardware-test.sh record-agent-direct-policy-review \
  --stable-support-gate <stable-support-gate-device-fingerprint.json> \
  --output-dir <local-output-dir>
```

This writes `agent-direct-policy-review.json`. The command runs offline,
validates the stable-support gate first, records the stricter agent defaults
from the safety policy, keeps printer identity out of this follow-up record,
keeps stdout status-only, and still sets `agentDirectPrintingEnabled: false`.
The policy review records direct printing as disabled by default, approval
required by default, long direct prints requiring approval, over-limit behavior
as preview-and-ask, no automatic retry after printable bytes, and no raw BLE
writes or unsafe resume.

Inspect the policy review before relying on it:

```bash
scripts/hardware-test.sh inspect-agent-direct-policy-review <agent-direct-policy-review.json>
```

The CLI inspection rejects records that expose raw device ids, omit
stable-support source validation, weaken approval requirements, change the
conservative agent limits, allow raw BLE writes or unsafe resume, or enable
agent direct printing. In the desktop app, use `Inspect agent-direct policy
review` in the Printer panel to show the gate while keeping explicit user opt-in
as the next required stage.

Record the explicit user opt-in gate from the agent-direct policy review:

```bash
scripts/hardware-test.sh record-agent-direct-user-opt-in \
  --agent-direct-policy-review <agent-direct-policy-review.json> \
  --confirm-explicit-user-opt-in \
  --output-dir <local-output-dir>
```

This writes `agent-direct-user-opt-in.json`. The command runs offline, validates
the policy-review gate first, requires the explicit confirmation flag, keeps
printer identity out of the follow-up record, and keeps stdout status-only. The
record changes the agent direct-print default from disabled to
approval-required, keeps over-limit behavior as preview-and-ask, and continues
to block unattended agent printing, raw BLE writes, and unsafe resume.

Inspect the opt-in record before relying on it:

```bash
scripts/hardware-test.sh inspect-agent-direct-user-opt-in <agent-direct-user-opt-in.json>
```

The CLI inspection rejects records that expose raw device ids, omit local
policy-review validation, weaken approval-required defaults, change the
conservative agent limits, allow unattended printing, allow raw BLE writes, or
allow unsafe resume. In the desktop app, use `Inspect agent-direct user opt-in`
in the Printer panel to show the opt-in gate. After inspection, the desktop app
copies the reviewed gate into its runtime handoff so MCP `print_note` can enforce
the gate automatically when agents omit the JSON argument. The tool still returns
approval-required preview metadata only.

## Shareable Evidence Summary

Use the offline evidence summary when asking maintainers to review Stage A
evidence before sharing a full artifact. The summary is not certification; it is
only a redacted checklist that confirms the Stage A artifact passed read-only
safety checks and records the deterministic Stage B/C preflight metadata.

The Electron Printer panel shows the same summary after `Inspect Stage A
artifact`. A summary is suitable for maintainer review only when it reports
`shareable: true`, `device.idRedacted: true`, and redaction flags showing local
paths, raw logs, command hex payloads, bearer tokens, and raster bytes are not
included.

## Long-Print Test Fixture

The renderer toolbar includes `Insert long-print test markers` for preparing a
deterministic continuous-paper fixture before later physical reliability tests.
The command extends the document to 8000 dots and inserts visible
`START LP-TEST`, 25%, 50%, 75%, and `END LP-TEST checksum: 7F3A` markers.

This fixture helps compare the preview, band plan, and physical output. It does
not unlock trusted printing or replace the Stage B, tiny visual card, or
long-print reliability hardware runs.
