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
- Agent direct printing is disabled by default.

## Preview Binding

The daemon creates preview-bound approval artifacts. Print planning requires a matching
preview id, document hash, render settings hash, raster hash, and approval token.
Diagnostics exports must not expose approval tokens or raw raster bytes.

## Runtime Boundaries

- Electron renderers use context isolation, sandboxing, and a narrow preload API.
- The daemon binds to localhost and requires bearer-token auth.
- MCP clients call the daemon through the stdio shim.
- Runtime state, logs, diagnostics, previews, and jobs are ignored by git.

## Hardware Artifacts

Hardware-test artifacts are shareable validation records after redaction. Stage A
artifacts must show `printCommandsSent: false`, `rasterBytesIncluded: false`,
`printingLocked: true`, and `certificationComplete: false`.
