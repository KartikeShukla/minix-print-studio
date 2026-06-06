# Safety

MiniX Print Studio treats thermal printing as a physical side effect. Previewing and
planning are separate from printing, and detected hardware is not trusted until the
explicit certification stages pass.

## Printing Gates

- BLE detection never grants print permission.
- Stage A read-only verification cannot move paper and cannot unlock printing.
- Stage B protocol sanity testing is a physical test and requires review of the
  offline preflight plan first.
- Tiny visual cards and long-print reliability tests require user confirmation.
- A trusted-printer record from reviewed Stage A/B/C artifacts enables only manual
  continuous printing; long-print output and stable support claims remain
  disabled until long-print reliability passes and a stable-support gate record is
  created from reviewed Stage D evidence.
- A stable-support gate record may enable long-print continuous printing and
  stable support claims, but it still keeps agent direct printing disabled by
  default.
- An agent-direct policy-review record may document stricter agent defaults,
  approval requirements, conservative limits, raw BLE write blocks, and unsafe
  resume blocks, but it still keeps direct printing disabled until a later
  explicit user opt-in workflow exists.
- A daemon result of `completed_unverified` means the BLE transfer finished from
  the daemon's perspective; it does not certify that the paper output is correct.
- Agent direct printing is disabled by default, and MCP print tools return
  approval-required responses with policy reasons instead of silently skipping
  the policy decision.

## Preview Binding

The daemon creates preview-bound approval artifacts. Print planning requires a matching
preview id, document hash, render settings hash, raster hash, and approval token.
Diagnostics exports must not expose approval tokens or raw raster bytes.

## Thermal Coverage Policy

Canonical preview rendering uses the selected printer profile's safety thresholds.
The daemon recomputes safety for both document-rendered previews and raw raster
preview submissions instead of trusting client-provided safety fields. Dense
output can still generate a preview artifact for review, but a preview with
`allowed: false` is refused by both print planning and direct print submission.
The renderer keeps the blocked preview's coverage, warnings, and errors visible
without enabling Print.

MCP preview and print-note responses preserve daemon safety metrics when the
preview is created, while still redacting approval tokens.

## Thermal Pacing

Long-print planning uses the selected profile's thermal pacing defaults before
any BLE transport sends data. Each planned band records its black-dot count,
black coverage, and `cooldownAfterMs` delay. The delay is redacted planning
metadata, not proof that hardware has accepted the output; physical transport
must still honor it and keep completion confidence conservative until the
hardware certification stages pass.

## Runtime Boundaries

- Electron renderers use context isolation, sandboxing, and a narrow preload API.
- The daemon binds to localhost and requires bearer-token auth.
- MCP clients call the daemon through the stdio shim.
- Runtime state, logs, diagnostics, previews, and jobs are ignored by git.

## Hardware Artifacts

Hardware-test artifacts are shareable validation records after redaction. Stage A
artifacts must show `printCommandsSent: false`, `rasterBytesIncluded: false`,
`printingLocked: true`, and `certificationComplete: false`.
Prefer the Stage A evidence summary for maintainer review before sharing a full
ZIP. The summary redacts the raw device id, omits artifact paths and raw logs, and
keeps command payload hex and raster bytes out of the shared data.
