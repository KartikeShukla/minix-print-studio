# MiniX Print Studio — Electron + shadcn Implementation Plan Spec

Status: full product implementation plan  
Project shape: new production-grade project, with selective migration from the existing MVP  
Primary target printer: Seznik MiniX BLE printer shown in the screenshot  
Confirmed device identifiers from screenshot/repo: `Seznik MiniX_0194_LE`, model response `S1_LYiN48D_GY`, firmware `V1.9.11`, BLE service `0000ff00-0000-1000-8000-00805f9b34fb`, write characteristic `0000ff02-0000-1000-8000-00805f9b34fb`, notify characteristics `0000ff01...` and `0000ff03...`  
Desktop decision: Electron  
UI decision: React + Vite + TypeScript + Tailwind + shadcn/ui  
Canvas decision: custom Figma/Photoshop-style editor built on React Konva, with backend-canonical preview/print rendering  
MCP decision: stdio-first MCP server, plus optional local Streamable HTTP for advanced/debug mode only

---

## 1. Product goal

Build a polished, installable desktop app that lets a user connect to the supported MiniX thermal printer, visually design printable receipts/labels/notes, safely preview the exact one-bit thermal output, and print without needing to understand BLE, raster packing, or protocol details.

The app must also expose a safe MCP connector so AI apps such as Codex, Claude Desktop, Claude Code, OpenCode, Cursor-like IDE agents, and other MCP clients can generate or request prints through a consistent local tool interface.

The output should feel like a small creative tool, not a developer demo. The workspace should be visual, direct-manipulation based, and closer to Figma/Photoshop than a form-based receipt generator.

---

## 2. Non-negotiable decisions

### 2.1 Build a new proper project

Do not mutate the existing repository into the product. Treat the current repo as source material and migrate only the proven parts:

- BLE profile knowledge.
- AiYin/LuckPrinter-style protocol sequence.
- Raster packing behavior.
- Safety thresholds and tests as a starting point.
- Mock BLE test design.
- Existing MCP tool ideas.
- Existing docs and compatibility notes.

Create a new clean monorepo with explicit boundaries between desktop shell, UI, daemon, protocol, renderer, safety, MCP, tests, packaging, and docs.

### 2.2 Electron is the desktop shell

Electron owns the desktop window, app lifecycle, tray/menu behavior, update checks, app settings UI, local daemon lifecycle, and safe IPC to the renderer.

Electron must not own printer protocol logic. Printer logic belongs in the daemon/core layer.

### 2.3 shadcn/ui is the UI system

Use shadcn/ui for the application chrome, panels, settings, dialogs, forms, command menu, toasts, sidebars, data tables, confirmation flows, integration screens, and onboarding.

The canvas itself is not a shadcn component. The canvas is a custom editor surface embedded inside a shadcn-based layout.

### 2.4 Your printer is first-class, others are explicit

The app should fully support your printer. Any other printer support must be model-specific, profile-specific, and test-gated. No broad claim such as “supports all FF00 thermal printers.”

A printer may be visible in scan results without being printable. A printer becomes printable only after:

1. It matches a known profile by service UUID and/or name.
2. It returns a known model and firmware response, when available.
3. It passes the supported-printer test workflow.
4. The user confirms that the printed test card matches the expected preview.

### 2.5 Continuous paper is default

Default paper mode is continuous. Gap-label and black-mark modes must be exposed as available configuration options, but only shown as fully supported after hardware tests confirm behavior on the actual printer/profile.

### 2.6 MCP installation is explicit

The app must generate copyable MCP configs. It may offer “Install into Codex,” “Install into Claude,” or “Install into OpenCode,” but those buttons must:

- Show the exact config that will be written.
- Show the file path that will be modified.
- Create a backup first.
- Require explicit user confirmation.
- Provide an uninstall/revert action.

### 2.7 Long prints must be reliable by design

Long receipts, notes, labels, and agent-generated outputs must not depend on one huge raster write plus a fixed final timeout. The app must plan long jobs, segment them, pace BLE writes, expose accurate progress, add a final feed margin, use dynamic timeouts, classify unknown outcomes honestly, and include hardware tests that specifically check for end cutoff.

---

## 3. Research basis

This plan assumes these current ecosystem facts:

- Electron apps should keep renderer processes isolated, with Node integration disabled and context isolation enabled. Electron’s own security guide states context isolation is the default since Electron 12 and that `nodeIntegration: false` alone is not enough without context isolation.
- electron-builder can package Electron apps for macOS, Windows, and Linux, supports auto-update, and supports code signing/notarization workflows.
- PyInstaller can package Python apps for Windows, macOS, and Linux but is not a cross-compiler; build each OS artifact on that OS.
- Bleak is a cross-platform Python BLE GATT client library.
- BLE writes must account for response semantics, negotiated payload limits, characteristic capabilities, and OS backend behavior. Write-with-response is slower but acknowledged by the remote device; write-without-response is faster but can queue locally and return before the peripheral has consumed the data.
- BLE MTU and data-length limits are negotiated between devices. If peer capability is unknown, the implementation should assume conservative packet sizes and avoid oversized writes.
- ESC/POS-style raster commands encode width and height in command parameters, and practical limits can be printer-specific. Long thermal output should be split into profile-tested bands rather than assuming one raster command can safely carry arbitrary height.
- MCP currently defines stdio and Streamable HTTP as standard transports. stdio is the safest default for local agent apps because the client launches the server subprocess.
- MCP tool calls are model-controlled, so sensitive operations should keep a human in the loop and should rate-limit, validate, and log tool invocations.
- Codex stores MCP server configuration in `~/.codex/config.toml` or trusted project-level `.codex/config.toml`.
- Claude Code can add MCP servers from JSON, import servers from Claude Desktop, and use `/mcp` to inspect configured servers.
- Claude Desktop now supports desktop extensions as `.mcpb` packages for one-click installation of local MCP servers.
- OpenCode stores MCP servers under the `mcp` key in its config and supports local servers using `type: "local"` with a command array.
- shadcn/ui supports Vite projects and is a code-distribution system rather than a traditional opaque component library.
- Konva/React Konva supports draggable, transformable canvas objects and official React bindings. Fabric.js and tldraw are valid alternatives, but React Konva is the better primary fit here because the app needs a constrained print artboard with custom thermal semantics rather than a general whiteboard.

Source URLs are listed at the end of this document.

---

## 4. Product name and user-facing positioning

Working name: **MiniX Print Studio**

User-facing promise:

> Design and print safe thermal notes, labels, receipts, QR codes, and agent-generated snippets on your MiniX printer.

Developer-facing promise:

> A local print daemon and MCP connector for model-specific BLE thermal printers, with canonical rendering, safety validation, and agent-safe print tools.

---

## 5. Final user experience

### 5.1 First launch

1. User installs the app.
2. User opens app.
3. App runs a local daemon sidecar.
4. App asks for Bluetooth permission when needed.
5. App scans for printers.
6. App shows detected printers with support confidence:
   - Fully supported.
   - Likely compatible but untested.
   - Unknown/unsupported.
7. User selects their printer.
8. App connects and queries model/firmware.
9. App runs read-only checks.
10. App asks user to run a tiny support test print.
11. User confirms the test card matches the preview.
12. App saves the printer as trusted.
13. User lands in the design workspace.

### 5.2 Normal manual print flow

1. User creates or opens a project.
2. User edits on a Figma-like fixed-width receipt artboard.
3. The UI continuously shows:
   - Visual canvas.
   - Exact one-bit preview.
   - Coverage meter.
   - Safety warnings.
   - Printer state.
4. User clicks Print.
5. Backend renders canonical raster from document JSON.
6. Backend computes safety decision.
7. App shows exact print preview.
8. User confirms.
9. Print job is queued.
10. Daemon executes a print plan: splits the approved raster into verified bands, sends each band with adaptive BLE pacing, applies cooldown when needed, waits for drain/completion criteria, and never marks success on an uncertain tail.
11. App shows result, logs, completion confidence, and reprint/recover options.

### 5.3 Agent print flow

1. User enables MCP in Settings > Agent Integrations.
2. App generates a stable `minix-mcp` shim path.
3. User copies or installs config into Codex/Claude/OpenCode.
4. Agent calls semantic MCP tools such as `print_note`, `preview_document`, or `print_qr_label`.
5. MCP connector sends the request to the local daemon.
6. Daemon validates source, policy, document, and printer state.
7. If safe and direct printing is enabled, daemon queues the job.
8. If approval is required, daemon returns an approval URL and preview ID.
9. User approves inside MiniX Print Studio.
10. The print proceeds using the exact approved preview hash.

---

## 6. Target architecture

```text
MiniX Print Studio
├─ Electron main process
│  ├─ app lifecycle
│  ├─ tray/menu
│  ├─ daemon supervisor
│  ├─ secure preload IPC
│  ├─ auto-update/check-for-update
│  └─ integration installer with explicit confirmation
│
├─ React renderer
│  ├─ shadcn app shell
│  ├─ Figma-like canvas editor
│  ├─ preview/safety panel
│  ├─ printer setup wizard
│  ├─ agent integration screens
│  ├─ diagnostics
│  └─ settings
│
├─ Local daemon sidecar
│  ├─ FastAPI local API
│  ├─ BLE scanner/connection manager
│  ├─ printer profile registry
│  ├─ protocol engine
│  ├─ canonical renderer
│  ├─ raster packer
│  ├─ safety engine
│  ├─ print queue
│  ├─ project/asset store
│  ├─ approval store
│  └─ diagnostics exporter
│
├─ MCP stdio shim
│  ├─ official MCP SDK / FastMCP implementation
│  ├─ semantic print tools
│  ├─ local daemon client
│  └─ no direct BLE access
│
└─ User data
   ├─ config
   ├─ trusted printer records
   ├─ projects
   ├─ assets
   ├─ preview cache
   ├─ job logs
   ├─ integration backups
   └─ diagnostics bundles
```

---

## 7. New monorepo structure

```text
minix-print-studio/
├─ package.json
├─ pnpm-workspace.yaml
├─ turbo.json
├─ README.md
├─ LICENSE
├─ SECURITY.md
├─ docs/
│  ├─ architecture.md
│  ├─ printer-profiles.md
│  ├─ hardware-certification.md
│  ├─ mcp-integrations.md
│  ├─ safety.md
│  ├─ release.md
│  └─ troubleshooting.md
│
├─ apps/
│  ├─ desktop/
│  │  ├─ electron.vite.config.ts
│  │  ├─ src/main/
│  │  │  ├─ main.ts
│  │  │  ├─ daemonSupervisor.ts
│  │  │  ├─ appMenu.ts
│  │  │  ├─ tray.ts
│  │  │  ├─ ipc.ts
│  │  │  ├─ updater.ts
│  │  │  ├─ integrationInstaller.ts
│  │  │  └─ paths.ts
│  │  ├─ src/preload/
│  │  │  └─ index.ts
│  │  ├─ resources/
│  │  │  ├─ icons/
│  │  │  └─ sidecars/
│  │  └─ electron-builder.yml
│  │
│  └─ renderer/
│     ├─ index.html
│     ├─ vite.config.ts
│     ├─ components.json
│     ├─ src/
│     │  ├─ app/
│     │  ├─ components/ui/             # shadcn components
│     │  ├─ components/app-shell/
│     │  ├─ features/workspace/
│     │  ├─ features/canvas/
│     │  ├─ features/preview/
│     │  ├─ features/printer-setup/
│     │  ├─ features/agent-integrations/
│     │  ├─ features/projects/
│     │  ├─ features/diagnostics/
│     │  ├─ features/settings/
│     │  ├─ lib/api-client.ts
│     │  ├─ lib/shortcuts.ts
│     │  └─ styles/globals.css
│     └─ tests/
│
├─ packages/
│  ├─ design-model/
│  │  ├─ src/schema.ts
│  │  ├─ src/types.ts
│  │  ├─ src/migrations.ts
│  │  └─ src/defaults.ts
│  │
│  ├─ canvas-engine/
│  │  ├─ src/EditorStage.tsx
│  │  ├─ src/tools/
│  │  ├─ src/layers/
│  │  ├─ src/selection/
│  │  ├─ src/snapping/
│  │  ├─ src/history/
│  │  └─ src/hotkeys/
│  │
│  ├─ shared-api/
│  │  ├─ src/schemas.ts
│  │  └─ src/events.ts
│  │
│  └─ integration-configs/
│     ├─ src/codex.ts
│     ├─ src/claudeDesktop.ts
│     ├─ src/claudeCode.ts
│     ├─ src/opencode.ts
│     └─ src/common.ts
│
├─ daemon/
│  ├─ pyproject.toml
│  ├─ src/minixd/
│  │  ├─ __main__.py
│  │  ├─ app.py
│  │  ├─ api/
│  │  ├─ ble/
│  │  ├─ protocol/
│  │  ├─ profiles/
│  │  ├─ render/
│  │  ├─ raster/
│  │  ├─ safety/
│  │  ├─ queue/
│  │  ├─ projects/
│  │  ├─ approvals/
│  │  ├─ diagnostics/
│  │  └─ integrations/
│  ├─ tests/
│  └─ pyinstaller/
│
├─ mcp/
│  ├─ pyproject.toml
│  ├─ src/minix_mcp/
│  │  ├─ __main__.py
│  │  ├─ server.py
│  │  ├─ tools.py
│  │  ├─ daemon_client.py
│  │  └─ schemas.py
│  └─ tests/
│
├─ profiles/
│  ├─ schema/printer-profile.schema.json
│  ├─ seznik-minix-s1-lyin48d-gy/profile.json
│  ├─ seznik-minix-s1-lyin48d-gy/tests.json
│  └─ README.md
│
├─ templates/
│  ├─ built-in/
│  └─ schema/template.schema.json
│
├─ scripts/
│  ├─ dev.sh
│  ├─ build-daemon.sh
│  ├─ build-mcp.sh
│  ├─ package-mac.sh
│  ├─ package-windows.ps1
│  ├─ lint-all.sh
│  └─ hardware-test.sh
│
└─ .github/workflows/
   ├─ ci.yml
   ├─ build-macos.yml
   ├─ build-windows.yml
   └─ release.yml
```

---

## 8. Runtime process model

### 8.1 Electron main process

Responsibilities:

- Start local daemon sidecar.
- Allocate and pass local auth token.
- Wait for daemon health.
- Restart daemon if it crashes unexpectedly.
- Shut daemon down when the app exits unless background MCP mode is enabled.
- Manage OS menus, tray, window state, update check, and logs.
- Provide a minimal preload API to renderer.
- Never expose shell, filesystem, or arbitrary process APIs to renderer.

Required Electron security settings:

```ts
new BrowserWindow({
  webPreferences: {
    preload: path.join(__dirname, "preload.js"),
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true,
  },
})
```

Renderer should call only typed preload APIs such as:

```ts
window.minix.getAppVersion()
window.minix.getDaemonRuntime()
window.minix.openExternalSafe(url)
window.minix.installIntegrationPreview(target)
window.minix.installIntegrationConfirmed(target, patchId)
```

All printer, project, and job operations should go through the daemon API, not Electron IPC.

### 8.2 Daemon sidecar

The daemon binds only to `127.0.0.1` on a random available port. The port and auth token are written to a runtime file:

```json
{
  "version": 1,
  "pid": 12345,
  "baseUrl": "http://127.0.0.1:39281",
  "tokenFile": "<user-data>/MiniX Print Studio/runtime/token",
  "startedAt": "2026-06-04T10:00:00Z"
}
```

All daemon API calls require a bearer token, including localhost calls. The renderer receives the token only via Electron preload, not from global JS variables.

### 8.3 MCP shim

The MCP shim is a stable executable path installed into user data, for example:

macOS:

```text
~/Library/Application Support/MiniX Print Studio/bin/minix-mcp
```

Windows:

```text
%APPDATA%\MiniX Print Studio\bin\minix-mcp.exe
```

The shim:

- Starts as a stdio MCP server.
- Reads daemon runtime info.
- Calls daemon over localhost with token.
- Does not directly scan BLE or print BLE.
- If daemon is not running:
  - Starts it only if user enabled “Allow agents to start background service,” or
  - Returns a structured `app_not_running` error with instructions.

---

## 9. Printer support strategy

### 9.1 Primary supported profile

Create this profile as the first official supported profile:

```json
{
  "id": "seznik-minix-s1-lyin48d-gy",
  "displayName": "Seznik MiniX — S1_LYiN48D_GY",
  "supportLevel": "official",
  "profileVersion": "1.0.0",
  "manufacturer": "unknown-or-confirm-after-user-input",
  "modelResponse": "S1_LYiN48D_GY",
  "observedFirmware": ["V1.9.11"],
  "namePrefixes": ["Seznik MiniX"],
  "ble": {
    "serviceUuid": "0000ff00-0000-1000-8000-00805f9b34fb",
    "writeCharUuid": "0000ff02-0000-1000-8000-00805f9b34fb",
    "notifyCharUuids": [
      "0000ff01-0000-1000-8000-00805f9b34fb",
      "0000ff03-0000-1000-8000-00805f9b34fb"
    ],
    "defaultChunkSize": 90,
    "minChunkSize": 20,
    "maxTestedChunkSize": 90,
    "writeWithResponse": true,
    "defaultInterChunkDelayMs": 25,
    "flowControlNotifyCharUuid": "0000ff03-0000-1000-8000-00805f9b34fb"
  },
  "readOnly": {
    "modelCommandHex": "10 ff 20 f0",
    "firmwareCommandHex": "10 ff 20 f1",
    "responseEncoding": "ascii-substring"
  },
  "print": {
    "protocol": "aiyin-gs-v0-wrapper",
    "widthDots": 384,
    "rowBytes": 48,
    "bitOrder": "msb-first",
    "blackBit": 1,
    "defaultPaperMode": "continuous",
    "paperModes": ["continuous", "gap_label", "black_mark"],
    "densityModes": ["light", "medium", "dark"],
    "defaultDensity": "medium",
    "longPrint": {
      "transferMode": "banded_gs_v0",
      "longPrintThresholdDots": 1200,
      "defaultMaxBandHeightDots": 256,
      "appendTailBlankRowsContinuous": 160,
      "finalAckPolicy": "required_for_confirmed_optional_for_unverified",
      "supportsResume": false,
      "pauseOnlyBetweenBands": true
    }
  },
  "safety": {
    "maxHeightDotsManual": 1600,
    "maxHeightDotsAgentDirect": 1000,
    "maxCopiesAgentDirect": 1,
    "warnTotalBlackCoverage": 0.35,
    "blockAgentTotalBlackCoverage": 0.45,
    "blockBandCoverage": 0.70,
    "bandHeightDots": 64
  }
}
```

### 9.2 Support levels

Use these exact support labels:

| Level | Meaning | User can print? |
|---|---|---:|
| `official` | Tested by us on a physical unit and firmware. | Yes |
| `community_verified` | Same model/profile validated by multiple external diagnostics and test prints. | Yes, with notice |
| `experimental` | Profile exists but not enough validation. | Only after explicit opt-in and test print |
| `detected_unverified` | BLE shape looks related, but model/profile not certified. | No direct printing |
| `unsupported` | App can see the device but cannot safely drive it. | No |

### 9.3 No generic support claims

The app may display:

> This device exposes a familiar FF00 BLE service, but that does not prove print compatibility. Run the compatibility test or add a model-specific profile before printing.

It must not display:

> This FF00 printer is supported.

### 9.4 Supported-printer testing workflow

The test workflow should have five stages.

#### Stage A — Read-only BLE verification

- Scan by service UUID and name.
- Connect.
- Discover services and characteristics.
- Subscribe to notify characteristics.
- Query model.
- Query firmware.
- Query battery/status if known.
- Save raw notification logs.

No paper movement in this stage.

#### Stage B — Protocol sanity test

- Send wake.
- Send density command for current default.
- Send paper mode command for continuous.
- Do not send raster yet.
- Confirm no error/unknown fatal response.

If this test produces unwanted paper movement, mark the command behavior in diagnostics.

#### Stage C — Tiny visual print card

Print a low-coverage card such as:

```text
MINIX TEST 7K4P
| left edge                right edge |
[thin checker pattern]
[small QR-like but low-density marker]
```

Height should be low, for example 120–180 dots. Use light/medium density and conservative chunk pacing.

User is shown the expected preview and must answer:

- Is the text readable?
- Are left/right edges visible?
- Is the output upside down?
- Is the output mirrored?
- Did the paper feed normally?
- Did the printer overheat, stall, disconnect, or flash an error?

#### Stage D — Long-print reliability test

Only after the tiny continuous card works:

- Print a low-coverage long strip with numbered markers at fixed intervals.
- Include `START`, `MID`, and `END` markers.
- Include a diagonal seam line that crosses raster-band boundaries.
- Include a final tiny text line immediately before the protected tail-feed area.
- App records bytes sent, rows sent, bands sent, flow-control notifications, finalizer status, and final ACK/status behavior.
- User confirms whether the `END` marker and final line are visible and whether the app reported the correct final state.

This test certifies the profile's `defaultMaxBandHeightDots`, `appendTailBlankRowsContinuous`, chunk size, inter-chunk delay, and final ACK policy for the specific printer/firmware.

#### Stage E — Optional paper mode tests

Only after continuous and long-print tests work:

- Gap-label test.
- Black-mark test.
- Label height calibration.
- Feed alignment check.

These should be per-paper and per-printer settings, not global.

### 9.5 Hardware certification artifact

Each hardware test run generates:

```text
hardware-test-<date>.zip
├─ device.json
├─ profile.json
├─ ble-discovery.json
├─ model-response.bin
├─ firmware-response.bin
├─ notifications.log
├─ commands.log
├─ raster-preview.png
├─ packed-raster.bin
├─ print-transfer-manifest.json
├─ band-manifest.json
├─ finalizer-result.json
├─ safety-report.json
├─ user-confirmation.json
└─ app-version.json
```

This bundle should be safe to share after redacting MAC address and user paths.

---

## 10. Printer protocol baseline

Use the known AiYin/LuckPrinter-style sequence from the existing project:

```text
set density:       10 ff 10 00 <density>
set paper mode:    10 ff 84 <paper>
wake:              00 repeated 12 times
enable mode:       10 ff fe 01
raster:            1d 76 30 00 xL xH yL yH <packed raster>
feed form:         1d 0c
stop mode:         10 ff fe 45
wait for OK
```

Supported command-facing options in profile v1:

```ts
type PaperMode = "continuous" | "gap_label" | "black_mark"
type Density = "light" | "medium" | "dark"
```

Known byte mapping from existing implementation:

```text
paper: gap_label=0x00, black_mark=0x01, continuous=0x02
density: light=0x00, medium=0x01, dark=0x02
```

### 10.1 Long-job protocol strategy

Small jobs may be printed as a single `GS v 0` raster command after hardware validation. Long jobs must not rely on one very tall raster payload.

The default long-job strategy is **banded GS v 0**:

1. Render the complete approved raster.
2. Append continuous-mode protected blank tail rows to the approved raster.
3. Slice the raster into bands no taller than `profile.print.longPrint.defaultMaxBandHeightDots`.
4. Send each band as an independent `GS v 0` raster command with its own width/height header.
5. Do not insert feed commands between bands unless the profile explicitly requires it.
6. Apply pacing and thermal cooldown between bands.
7. Send the profile-specific finalizer after all bands.
8. Classify completion using the explicit completion-state model, not just a single final `OK` timeout.

Banding is mandatory for reliability because it gives the app safe pause points, clearer progress, smaller command payloads, better diagnostics, and a place to apply thermal cooldown. Arbitrary mid-band resume is disabled in v1 because the printer's internal stream/buffer state is not observable enough to avoid duplicate or corrupted output.

### 10.2 Finalizer strategy

For continuous paper, the product must not rely only on a post-print feed command to prevent bottom cutoff. The canonical raster should include protected blank tail rows, then the daemon can additionally send a profile-specific final feed/form/stop sequence.

Finalizer result categories:

| Result | Meaning | User-facing result |
|---|---|---|
| `confirmed_complete` | All bands sent, finalizer sent, terminal OK/status received. | Completed |
| `complete_unverified` | All bands and finalizer were sent, but terminal OK/status timed out or was ambiguous. | Needs user check, not generic failed |
| `tail_feed_uncertain` | All raster bands sent, final feed/form failed or timed out. | Output may be complete; offer safe Feed Paper action |
| `partial_transfer` | Failure before all raster bands were accepted by the BLE stack. | Failed partial print |
| `unknown_after_disconnect` | Disconnect occurred after some non-idempotent data was sent. | Needs inspection; no automatic reprint |

The UI and MCP responses must distinguish these states. A final ACK timeout after the raster transfer should not be shown as the same failure as a disconnect halfway through the job.

### 10.3 BLE ownership rule

Only the daemon may own the BLE connection in the production app. The Electron UI, MCP shim, CLI, and integrations must call the daemon API. They must not open direct BLE sessions except in an explicit developer diagnostic mode that first asks the daemon to release the printer.

This prevents stale daemon, fresh CLI, or agent bridge processes from fighting over the same BLE printer session.

Keep raw BLE disabled by default. Firmware/update-like prefixes remain blocked even if developer mode is enabled, unless a separate hidden unsafe environment flag is set.

---

## 11. UI architecture

### 11.1 App shell

Use a shadcn-style application layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ Top bar: project name, printer status, print button, command │
├───────────────┬───────────────────────────────┬──────────────┤
│ Left sidebar  │ Canvas workspace              │ Right panel  │
│ - Tools       │ - Artboard                    │ - Inspector  │
│ - Layers      │ - Guides/rulers               │ - Preview    │
│ - Templates   │ - Zoom/pan                    │ - Safety     │
│ - Assets      │                               │ - Settings   │
├───────────────┴───────────────────────────────┴──────────────┤
│ Status bar: zoom, dimensions, coverage, job queue, connection│
└──────────────────────────────────────────────────────────────┘
```

Use shadcn components for:

- Sidebar.
- Resizable panels.
- Tabs.
- Dialogs.
- Popovers.
- Dropdown menus.
- Command palette.
- Form controls.
- Data tables.
- Alerts.
- Toasts/Sonner.
- Sheets/drawers.
- Tooltips.
- Progress indicators.
- Confirmation dialogs.

### 11.2 Main sections

1. Workspace
2. Projects
3. Templates
4. Printer Setup
5. Job Queue
6. Agent Integrations
7. Diagnostics
8. Settings
9. Developer Mode

---

## 12. Canvas editor design

### 12.1 Canvas feel

The canvas should feel like a constrained print-focused version of Figma/Photoshop:

- Pan and zoom.
- Centered artboard.
- Rulers.
- Guides.
- Snaplines.
- Alignment hints.
- Resize handles.
- Rotate handles.
- Multi-select.
- Group/ungroup.
- Lock/hide layers.
- Layer order.
- Keyboard shortcuts.
- Context menus.
- Copy/paste.
- Drag/drop image import.
- Undo/redo.
- Inspector-based precise edits.
- Live preview panel.
- Pixel-level one-bit output view.

### 12.2 Why React Konva

Use React Konva for v1 because:

- It works directly with React.
- It supports object-level canvas rendering.
- It supports draggable objects.
- It has transform handles through `Konva.Transformer`.
- It supports layers.
- It gives enough low-level control to enforce a thermal printer artboard.
- It does not impose a whiteboard-centric document model.

Do not use tldraw as the main editor in v1. tldraw is strong for infinite whiteboards, but this product needs a thermal-specific fixed-width artboard, custom safety overlays, profile-specific output constraints, and canonical backend rendering.

Do not use Fabric.js as the main editor in v1 unless React Konva text editing/image editing becomes too slow to implement. Fabric is strong for image-editor object manipulation, SVG import/export, and filters, but React Konva is cleaner for a React-first app shell and custom editor state.

### 12.3 Canvas tools

Minimum v1 tool set:

| Tool | Behavior |
|---|---|
| Select | Click/drag, multi-select, move, resize, rotate |
| Pan | Space + drag, trackpad pan |
| Text | Draw text box, edit inline with HTML overlay |
| Rectangle | Fill/stroke, radius |
| Line | Stroke width, dash, arrow optional |
| Image | Import, crop, scale, dither/threshold settings |
| QR | Text/URL/data QR with safety-aware sizing |
| Barcode | Code128/EAN if needed later |
| Freehand | Simple path drawing with smoothing and safety cap |
| Frame/Section | Optional grouping/artboard region for templates |

### 12.4 Layer panel

Each document has ordered layers:

- Name.
- Type icon.
- Visible/hidden.
- Locked/unlocked.
- Coverage warning indicator.
- Out-of-bounds indicator.
- Drag reorder.
- Group nesting.

### 12.5 Inspector panel

Inspector should expose:

- X/Y/W/H in dots and mm.
- Rotation.
- Lock aspect ratio.
- Opacity/grayscale before one-bit rasterization.
- Fill/stroke.
- Font family, size, weight, alignment, line-height.
- Image threshold/dither/contrast/brightness/invert.
- QR payload and error correction.
- Safety summary for selected object.

### 12.6 Photoshop-like image controls

Image objects should support:

- Crop box.
- Fit/fill/contain.
- Brightness.
- Contrast.
- Gamma.
- Threshold.
- Invert.
- Dither algorithm:
  - none/threshold
  - Floyd-Steinberg
  - Atkinson
  - ordered Bayer
- Blur/sharpen if needed.
- Black coverage preview.
- “Make safer” button that reduces density/contrast or switches dither mode.

### 12.7 Figma-like layout controls

Objects should support:

- Align left/center/right.
- Align top/middle/bottom.
- Distribute vertical/horizontal.
- Snap to artboard edges.
- Snap to center line.
- Snap to object bounds.
- Duplicate with Alt/Option drag.
- Nudge 1 dot with arrow keys.
- Nudge 10 dots with Shift + arrow.
- Group/ungroup.
- Lock/hide.

### 12.8 Thermal-specific overlays

Canvas should always offer these overlays:

- Printable width boundary.
- Paper edge guide.
- Safe height guide.
- High-coverage heatmap.
- Dense-band warnings.
- One-bit preview ghost overlay.
- Out-of-bounds crop overlay.
- Paper mode guide for label/gap/black-mark modes.

---

## 13. Document model

### 13.1 Principles

The document model must be stable, versioned, and serializable. It should not be tied directly to Konva internals. Konva is only an editing surface.

All renderers, tests, MCP tools, and saved projects use the same document schema.

### 13.2 Document JSON skeleton

```json
{
  "schemaVersion": 1,
  "id": "doc_abc123",
  "title": "Untitled print",
  "createdAt": "2026-06-04T10:00:00Z",
  "updatedAt": "2026-06-04T10:00:00Z",
  "target": {
    "profileId": "seznik-minix-s1-lyin48d-gy",
    "widthDots": 384,
    "heightDots": 900,
    "dpi": 203,
    "paperMode": "continuous",
    "density": "medium"
  },
  "background": {
    "color": "#ffffff"
  },
  "elements": [
    {
      "id": "el_title",
      "type": "text",
      "name": "Title",
      "x": 24,
      "y": 32,
      "width": 336,
      "height": 80,
      "rotation": 0,
      "locked": false,
      "visible": true,
      "text": "Hello thermal world",
      "style": {
        "fontFamily": "Inter",
        "fontSize": 28,
        "fontWeight": 700,
        "align": "center",
        "lineHeight": 1.1,
        "fill": "#000000"
      }
    }
  ],
  "assets": [],
  "metadata": {}
}
```

### 13.3 Element types

Implement these element types in v1:

```ts
type ElementType =
  | "text"
  | "image"
  | "rect"
  | "line"
  | "path"
  | "qr"
  | "barcode"
  | "group"
```

### 13.4 Units

Internal units are printer dots.

Display units can be:

- dots
- mm
- inches

Use the profile DPI for conversion. If DPI is not confirmed for the physical printer, show “logical DPI” and allow calibration.

### 13.5 Migration

Every document has a schema version. Migrations live in `packages/design-model` and are tested with fixture documents.

---

## 14. Rendering pipeline

### 14.1 Two renderers, one source of truth

There are two renderers:

1. **Interactive renderer** in React Konva for live editing.
2. **Canonical renderer** in the daemon for preview and print.

Only the canonical renderer can produce a printable job.

### 14.2 Canonical preview-to-print binding

This is mandatory.

Flow:

1. User requests preview.
2. Daemon validates document schema.
3. Daemon renders grayscale image.
4. Daemon converts to one-bit thermal bitmap.
5. Daemon packs raster bytes.
6. Daemon computes safety report.
7. Daemon stores:
   - document hash
   - render settings hash
   - raster hash
   - preview PNG
   - safety report
8. Daemon returns `previewId` and `approvalToken`.
9. Print request must reference this preview ID.
10. Daemon refuses to print if document/settings changed after preview.

Example preview record:

```json
{
  "previewId": "prev_abc123",
  "documentHash": "sha256:...",
  "rasterHash": "sha256:...",
  "profileId": "seznik-minix-s1-lyin48d-gy",
  "widthDots": 384,
  "heightDots": 900,
  "safety": {
    "allowed": true,
    "warnings": [],
    "metrics": {
      "totalBlackCoverage": 0.18,
      "maxBandCoverage": 0.42
    }
  },
  "expiresAt": "2026-06-04T10:10:00Z"
}
```

### 14.3 Canonical renderer implementation

Use Python/Pillow in the daemon for v1 because:

- The existing raster pipeline is Python.
- BLE transport is Python via Bleak.
- The MCP shim can reuse daemon API.
- PyInstaller can package the daemon with its Python runtime.

Renderer tasks:

- Load document JSON.
- Validate dimensions.
- Resolve fonts.
- Load assets by hash.
- Flatten layers.
- Render grayscale canvas at exact dot size.
- Apply object transforms.
- Apply image preprocessing.
- Render text with bundled fonts.
- Render QR/barcodes.
- Convert to one-bit.
- Pack MSB-first row bytes.
- Generate PNG preview and coverage heatmap.

### 14.4 Font policy

Bundle a small set of open-license fonts. Do not rely on system fonts for canonical output.

Initial font set:

- Inter or equivalent sans.
- A condensed sans for labels.
- A monospace font for receipts/code.

Every saved text element stores `fontFamily`, but the renderer maps it to a bundled font file. Missing fonts are replaced with a deterministic fallback and warning.

### 14.5 Image import policy

Accepted input:

- PNG
- JPEG
- WebP if available
- SVG only after sanitization, or convert through safe pipeline

Hard limits:

- Max imported image pixels.
- Max file size.
- Max SVG complexity.
- No remote image URLs in documents.
- Assets copied into project asset store by hash.

---

## 15. Safety engine

### 15.1 Safety objectives

Prevent:

- Excessive dense black output.
- Excessive continuous high-coverage bands.
- Unbounded height.
- Repeated agent-triggered prints.
- Raw command misuse.
- Firmware/update command misuse.
- Unexpected paper mode behavior.
- Printing without preview confirmation.
- Printing on an unverified printer.
- Long print truncation or end cutoff.
- False success after a post-send timeout.
- BLE buffer overrun caused by sending too fast.
- Unsafe automatic retry after partial physical output.

### 15.2 Safety stages

| Stage | Applies to | Examples |
|---|---|---|
| Schema validation | All jobs | width, height, asset bounds, required fields |
| Document validation | All jobs | out-of-bounds elements, missing assets, invalid fonts |
| Render validation | Preview/print | actual raster dimensions, packed row bytes |
| Coverage validation | Preview/print | total coverage, band coverage, black runs |
| Thermal budget | Print | cooldown, dense rows, per-job budget |
| Source policy | Agent/API/UI | direct print limits, approvals, copies |
| Printer policy | Print | supported profile, trusted device, paper mode |
| Runtime policy | Print | rate limit, connection state, response timeouts |

### 15.3 Required safety metrics

For every preview:

```json
{
  "heightDots": 900,
  "totalBlackPixels": 62208,
  "totalPixels": 345600,
  "totalBlackCoverage": 0.18,
  "maxBandCoverage64": 0.42,
  "maxConsecutiveDenseRows": 18,
  "longestHorizontalBlackRun": 210,
  "estimatedThermalBudget": 0.31,
  "warnings": [],
  "errors": []
}
```

### 15.4 Initial thresholds

Start conservative:

```json
{
  "manual": {
    "maxHeightDots": 1600,
    "warnTotalBlackCoverage": 0.35,
    "blockTotalBlackCoverage": 0.55,
    "blockBandCoverage": 0.75,
    "maxCopies": 5
  },
  "agentDirect": {
    "maxHeightDots": 1000,
    "warnTotalBlackCoverage": 0.30,
    "blockTotalBlackCoverage": 0.45,
    "blockBandCoverage": 0.70,
    "maxCopies": 1,
    "jobsPerMinute": 3
  }
}
```

These are policy defaults. Actual thresholds should live in the printer profile and can be updated after hardware testing.

### 15.5 Make safer actions

When content fails safety checks, offer actions:

- Lower density.
- Reduce contrast.
- Switch dither algorithm.
- Scale image down.
- Add whitespace between dense regions.
- Split into multiple prints with cooldown.
- Convert solid fills to patterns.
- Crop image.
- Reduce copies.

### 15.6 Agent safety policy

Agent direct printing is disabled by default.

User settings:

```json
{
  "agents": {
    "enabled": true,
    "directPrint": false,
    "allowTemplatesDirect": true,
    "allowImageDirect": false,
    "allowMarkdownDirect": false,
    "requireApprovalForHighCoverage": true,
    "requireApprovalForNewPrinter": true,
    "rateLimitJobsPerMinute": 3,
    "quietHours": null
  }
}
```

MCP direct-print tools should return approval-required responses when policy blocks direct printing.

---

## 16. Paper and printer configuration options

### 16.1 User-visible configuration

Expose these in Settings > Printer:

| Setting | Default | Notes |
|---|---|---|
| Printer alias | Device name | User-friendly label |
| Profile | Auto-detected | Locked unless developer mode |
| Paper mode | Continuous | Continuous, gap label, black mark |
| Density | Medium | Light, medium, dark |
| Default document height | 900 dots | User preference |
| Logical DPI | 203 | Calibration-dependent |
| Max manual height | Profile default | Safety-controlled |
| Max agent direct height | Profile default | Safety-controlled |
| Feed after print | Enabled | Uses known feed/form command |
| Protected tail margin | 160 dots | Continuous mode default; prevents bottom cutoff |
| Long-print reliability mode | Banded | Required for lengthy documents |
| Max band height | Profile default | Advanced/developer; locked for official profile |
| Final ACK policy | Profile default | Controls confirmed vs unverified completion |
| Idle BLE disconnect | Enabled | Daemon behavior only, not printer firmware |
| Auto reconnect | Enabled | App behavior |
| Chunk size | 90 | Advanced/developer |
| Inter-chunk delay | profile default | Advanced/developer |
| Write with response | true | Advanced/developer |
| Flow-control mode | Profile default | Advanced/developer |
| Long-print band height | Profile default | Advanced/developer; hardware-certified |
| Tail padding | Enabled | Prevents end cutoff |
| Completion timeout | Auto | Scales with height/density/coverage |

### 16.2 Paper modes

Continuous mode:

- Default.
- No label calibration required.
- Best for notes, receipts, quick prints, agent output.

Gap-label mode:

- Requires label height, gap height, and feed alignment testing.
- Should be disabled until tested on the user’s actual label stock.

Black-mark mode:

- Requires mark offset, mark height, and sensor behavior testing.
- Should be disabled until tested on the user’s actual paper.

### 16.3 Advanced/developer settings

Hide behind Developer Mode:

- Raw BLE console: disabled by default and heavily warned.
- Protocol step viewer.
- Command log export.
- Notification log viewer.
- Manual chunk size override.
- Manual band height override.
- Manual command timeout override.
- Final ACK policy override for diagnostics.
- Mock printer toggle.
- Hardware test runner.
- Profile editor.

Firmware/update-like commands remain blocked unless an unsafe environment variable is set outside the UI.

---

## 17. Long-print reliability and cutoff prevention

### 17.1 Problem statement

The previous project showed a critical long-print failure mode: lengthy content sometimes did not print fully, or the final portion was cut off while the software reported a failed print. The new app must treat this as a product-level reliability requirement, not as a generic BLE timeout bug.

The app should support long receipts, long notes, long markdown snippets, tall image compositions, and agent-generated content without silently dropping the tail. When the printer or BLE transport cannot complete the print reliably, the app should give an accurate failure state and recovery path.

### 17.2 Failure classes to design against

Do not assume there is one root cause. The implementation must protect against all of these:

| Failure class | Typical symptom | Required design response |
|---|---|---|
| Oversized raster command | Print starts, then stops before the end | Split raster into profile-tested bands |
| Printer input-buffer overflow | Random cutoff or disconnect during long transfer | Adaptive pacing, flow-control decoding, smaller chunks |
| BLE write accepted but printer still busy | Software thinks sending is done while paper continues | Separate `data_sent`, `finalizing`, and `confirmed` states |
| Missing final ACK / final OK timeout | Output appears complete but app says failed | `completed_unverified`, not generic failed |
| Fixed final timeout too short | Long print physically continues after timeout | Height-aware timeout based on dots, density, and coverage |
| Premature stop/form-feed | Last part missing or fed incorrectly | Delay finalizer until stream drain criteria are met |
| BLE disconnect mid-stream | Partial physical output | Phase-specific failure and no automatic duplicate reprint |
| Notification loss or unknown notification | Hang, false failure, or false success | Notifications are logged and interpreted only when profile-certified |
| High thermal load | Slow, faint, cut, or overheated output | Thermal budget, cooldown between dense bands, density downgrade |
| Missing bottom margin | Final visible content remains under head / near tear edge | Protected blank tail rows included in approved raster |
| Agent overlong output | Unbounded print from Codex/Claude/OpenCode | Agent height limits, preview approval, split suggestions |
| App close/sleep during job | Partial output and unclear state | Job lock, sleep prevention while printing, recovery on restart |
| Competing BLE owners | Daemon/CLI/MCP fight for printer | Single daemon BLE owner rule |
| Low battery / printer sleep | Drops connection near end | Preflight status/battery where known; long-print warning otherwise |

### 17.3 Reliability principles

Long-print correctness is based on these rules:

1. **Render once, print exact raster.** Preview-to-print binding still applies.
2. **Append protected blank tail rows.** Continuous-mode jobs include non-editable blank rows after content so the final visible line advances safely out of the print head.
3. **Slice into raster bands.** Long content is sent as multiple bounded-height raster bands instead of one giant payload.
4. **Persist a print plan and transfer manifest.** Every job records expected bands, bytes, rows, hashes, timings, notifications, and finalizer state.
5. **Track physical uncertainty.** The app distinguishes “bytes accepted by BLE,” “all bands sent,” “printer finalizer completed,” and “physical output verified.”
6. **No unsafe auto-resume.** v1 does not resume mid-band or automatically reprint after uncertain partial output.
7. **Pause only at safe boundaries.** Pause, cancel, and cooldown can happen between bands, not during an active BLE write chunk.
8. **Use conservative BLE settings first.** Official profiles start with write-with-response, tested chunk size, tested pacing, and profile-specific flow-control interpretation.

### 17.4 New print architecture

The daemon must not send the approved raster as one large untracked blob. It should create a deterministic **PrintPlan** from the approved preview artifact.

```text
Approved preview raster
  ↓
Print planner
  ↓
Protected tail-row append
  ↓
Band segmentation
  ↓
Safety and thermal budget per band
  ↓
BLE stream controller
  ↓
Finalizer and drain verifier
  ↓
Job result with confidence level
```

The print plan is part of the approved artifact. If the document, printer profile, density, paper mode, renderer version, or raster changes, the print plan is invalidated.

### 17.5 PrintPlan and transfer manifest schema

Create the plan before sending the first byte. Persist it to disk atomically so progress and diagnostics survive app refresh/restart.

```json
{
  "planId": "plan_abc123",
  "jobId": "job_abc123",
  "previewId": "prev_abc123",
  "documentHash": "sha256:...",
  "rasterHash": "sha256:...",
  "profileId": "seznik-minix-s1-lyin48d-gy",
  "firmware": "V1.9.11",
  "paperMode": "continuous",
  "density": "medium",
  "widthDots": 384,
  "contentHeightDots": 4200,
  "tailBlankRowsDots": 160,
  "transferHeightDots": 4360,
  "rowBytes": 48,
  "totalRasterBytes": 209280,
  "requiresLongPrintMode": true,
  "bands": [
    {
      "index": 0,
      "startRow": 0,
      "heightDots": 256,
      "rasterByteOffset": 0,
      "rasterByteLength": 12288,
      "payloadBytes": 12296,
      "sha256": "sha256:...",
      "estimatedCoverage": 0.12,
      "maxBandCoverage64": 0.31,
      "cooldownAfterMs": 0,
      "commandMode": "gs_v_0",
      "state": "pending"
    }
  ],
  "transport": {
    "writeMode": "with_response",
    "chunkSizeBytes": 90,
    "interChunkDelayMs": 25,
    "flowControl": "ff03_credit_or_timed_fallback",
    "adaptivePacing": true
  },
  "completion": {
    "finalAckPolicy": "required_for_confirmed_optional_for_unverified",
    "tailDrainTimeoutMs": 30000,
    "allowUnverifiedCompletion": true
  }
}
```

### 17.6 Band segmentation rules

Initial profile defaults for the MiniX printer should be conservative until hardware testing proves higher limits:

```json
{
  "longPrint": {
    "enabled": true,
    "longPrintThresholdDots": 1200,
    "defaultBandHeightDots": 256,
    "minBandHeightDots": 64,
    "maxBandHeightDots": 384,
    "maxSegmentRasterBytes": 18432,
    "tailBlankRowsContinuous": 160,
    "denseBandCooldownMs": 750,
    "maxConsecutiveDenseSegments": 3
  }
}
```

Segmentation rules:

1. A band must contain whole rows only.
2. `segment.rasterByteLength == rowBytes * segment.heightDots` must always hold.
3. Segments must cover every source row exactly once.
4. Segment order must be monotonic by `startRow`.
5. No segment may exceed the profile's tested maximum raster bytes.
6. No segment may exceed the profile's tested maximum raster height.
7. Dense segments may be smaller than sparse segments.
8. Tail blank rows are part of the approved raster, so the preview shows the true printed end.
9. Each segment has a hash for diagnostics and reconstruction.
10. A virtual printer test must reconstruct the full raster from segments and verify the hash equals the approved raster hash.

### 17.7 Raster command strategy

Default v1 strategy:

```text
For each band:
  build GS v 0 raster command header for that band height
  append only that band raster bytes
  stream band command through BLE flow controller
  wait for per-band pacing/drain rule
After final band:
  send configured feed/trailer command, if profile uses one
  send stop/end command
  wait for final completion rule
```

The profile should support multiple raster modes, but only enable modes after hardware tests:

| Mode | Status | Notes |
|---|---|---|
| `gs_v_0_banded` | Default candidate | Uses existing raster command style, but splits height into bands |
| `single_gs_v_0` | Diagnostic only | Useful as a comparison test, not default for long prints |
| `dc2_v_fixed_384` | Experimental | Some related command sets expose fixed-width 384-dot bitmap commands |

The test suite must verify that banded `GS v 0` output prints seamlessly on continuous paper. If it produces gaps, overlap, resets, or unexpected feed between bands, the profile must store the observed behavior and choose another profile-specific command mode.

### 17.8 BLE stream controller

Implement a dedicated stream controller instead of a simple `for chunk in chunks: write(); sleep()` loop.

Responsibilities:

- Inspect write characteristic properties at connection time.
- Prefer explicit `response=True` until write-without-response is hardware-certified.
- Use a characteristic object when possible, not only UUID strings, to avoid ambiguity if duplicate UUIDs appear.
- Determine safe chunk size from profile, write mode, and backend capability.
- Subscribe to notify characteristics before sending payload.
- Decode FF03-like flow-control notifications into credits only if semantics are confirmed.
- Use adaptive pacing when flow control is absent, delayed, or ambiguous.
- Reduce chunk size and increase delay after timeout, disconnect, or printer back-pressure.
- Track byte-level, row-level, segment-level, and notification-level progress.
- Emit structured progress events to UI and MCP callers.

Initial pacing policy:

```json
{
  "writeWithResponse": true,
  "baseChunkSizeBytes": 90,
  "minChunkSizeBytes": 20,
  "maxChunkSizeBytes": 180,
  "baseInterChunkDelayMs": 25,
  "maxInterChunkDelayMs": 150,
  "flowControlWaitMs": 80,
  "segmentDrainMs": 120,
  "backoffMultiplier": 1.5,
  "maxWriteRetriesBeforeDisconnect": 2
}
```

The final values must be established through hardware tests on the actual printer. The profile should store separate defaults for macOS and Windows if they differ.

### 17.9 Completion model

A job must not be marked as completed merely because all bytes were handed to the OS Bluetooth stack.

Required states:

```text
created
previewed
planned
queued
connecting
preflight
streaming_band
waiting_flow_control
band_drain
cooling_down
tail_drain
finalizing
waiting_for_final_status
completed_confirmed
completed_unverified
failed_before_output
failed_partial_output
failed_tail_uncertain
cancelled_before_output
cancelled_partial_output
needs_user_check
blocked_by_policy
```

Completion levels:

| Level | Meaning | User-facing result |
|---|---|---|
| `verified` | Final OK/status or profile-certified completion signal received after drain | Success |
| `unverified` | All bands and finalizer were sent, but no reliable final status exists or final ACK timed out | Likely printed; check output |
| `uncertain` | Bytes sent but disconnect/timeout occurred before completion criteria | Needs user check |
| `failed_before_output` | Failure occurred before printable payload began | Safe to retry |
| `failed_partial_output` | Failure occurred after printable payload began | Do not auto-retry |

For this printer, the profile should initially require final OK only if tests prove the OK arrives after physical completion rather than merely after command acceptance. If OK semantics are ambiguous, completion should use a conservative drain period and show `completed_unverified` until the profile is certified.

### 17.10 Height-aware timeouts

Do not use a fixed final timeout for every job.

The daemon should compute:

```text
tailDrainTimeoutMs = baseMs
                   + estimatedPrintTimeMs(heightDots, density, coverage)
                   + transportSlackMs
                   + batteryOrThermalSlackMs
```

Start with conservative defaults:

```json
{
  "completionTimeout": {
    "baseMs": 8000,
    "per1000DotsMs": 4500,
    "denseCoverageExtraMs": 5000,
    "maxMs": 120000
  }
}
```

These are not final physical constants. They are safe starting values that must be calibrated using real long-print tests.

### 17.11 Tail cutoff prevention

Every printable document needs a visible end model.

Rules:

1. The canvas shows the printable end boundary.
2. The canvas shows the non-editable protected tail zone for continuous paper.
3. The backend renderer appends profile-defined blank rows unless disabled in developer diagnostics.
4. Tail blank rows are included in preview hash and raster hash.
5. The print command sends a profile-defined final feed/trailer after the last segment if hardware testing confirms it is useful.
6. Completion waits for tail drain after the final band/finalizer.
7. Diagnostics record whether the last content segment, tail blank segment, and finalizer were sent and acknowledged.

Default for continuous mode:

```json
{
  "tailBlankRowsContinuous": 160,
  "postPrintFeedDots": 64,
  "showTailBlankRowsInPreview": true,
  "warnIfContentTouchesBottom": true
}
```

The UI should show warnings such as:

```text
Content is too close to the printable end. Add 12 mm of bottom padding to prevent cutoff.
```

For gap-label and black-mark modes, do not blindly append continuous blank rows. Tail behavior depends on label height, gap/mark offset, and calibration. Label mode must pass a separate final-line visibility test before being marked supported.

### 17.12 Long-print preflight

Before a long job starts, the daemon checks:

- Printer is still connected and matched to the trusted profile.
- Firmware/profile pair is still trusted.
- Battery/status is acceptable if status mapping is known.
- No other daemon/CLI/MCP process owns the BLE printer.
- Paper mode is continuous unless a label mode has passed long-output testing.
- Job height is within manual or agent policy.
- Thermal budget and band coverage are within limits.
- Tail blank rows are present and included in the approved raster.
- There is enough estimated time before idle disconnect or app shutdown.
- OS sleep prevention is active for the print duration.

### 17.13 Long-print UI behavior

The print dialog should change when a job enters long-print mode.

Show:

- Total height in dots and approximate paper length.
- Number of print bands.
- Added protected tail margin.
- Estimated print time.
- Coverage summary.
- Whether cooldown pauses are expected.
- A warning if printer status/battery is unknown.
- The exact preview that will be printed.

During print, show:

```text
Printing band 7 of 28
Rows 1152–1343 of 5320
Bytes sent 66,240 / 255,360
Waiting for printer to drain...
```

Final UI copy must distinguish:

- “Completed.”
- “Likely completed; final confirmation timed out.”
- “Partial output possible.”
- “Tail feed uncertain; output may be complete but may need paper feed.”

The workspace should include a developer/test command: **Insert long-print test markers**. This adds small row/section markers to a test document so lengthy-output issues can be reproduced deterministically.

### 17.14 Recovery, retry, resume, and cancel rules

Recovery depends on when the failure happened.

| Failure phase | Safe automatic action | User action |
|---|---|---|
| Scan/connect fails before print | Retry connect using policy | Rescan |
| Preflight fails | No print | Fix printer/paper/battery |
| Before first raster band | Retry may be offered | Retry |
| During first band | No automatic retry | Reprint whole job after inspection |
| During later band | No automatic retry | Advanced resume only after user confirms prior output |
| Between bands | No automatic retry in v1 | User check required before any resume |
| After all bands, before final OK | No automatic retry | Confirm whether paper finished printing |
| Tail feed failure | Safe feed action may be offered | Feed paper or reprint manually |
| After verified completion | None | Reprint only if user requests |

Cancel behavior:

- Cancel before first band is clean.
- Cancel during a band means “stop sending further data,” not “recall data already inside printer.”
- Cancel should send a stop command only if the profile marks it safe for the current phase.
- UI must state that the printer may continue printing already-buffered content.

### 17.15 Agent and MCP long-print behavior

Agent-originated jobs are stricter:

- No automatic retry after any printable byte is sent.
- Long direct prints require approval unless the user explicitly enables long direct prints for that agent.
- Agent direct-print height limit is lower than manual UI height limit.
- MCP responses include `jobState`, `completionConfidence`, `rowsSent`, `bandsSent`, and `requiresUserCheck`.
- Agents cannot request raw chunk size, raw BLE writes, or unsafe resume.

Example MCP result:

```json
{
  "jobId": "job_...",
  "jobState": "completed_unverified",
  "completionConfidence": "data_sent_final_ack_missing",
  "bandsSent": 18,
  "totalBands": 18,
  "rowsSent": 4360,
  "totalRows": 4360,
  "requiresUserCheck": true,
  "message": "All raster bands were sent, but the printer did not return a final confirmation. Check whether the END marker printed before reprinting."
}
```

### 17.16 Splitting extremely long content

For very long documents, the product should offer intentional splitting rather than trying to print everything as one physical stream.

Options:

```text
Print as one long strip
Print as N parts with separator headers
Print selected range
Export preview instead
Make shorter with AI/app tools
```

The split mode should insert small headers/footers only when the user chooses it, for example:

```text
Part 2 of 5
Rows 1800–3599
```

For agent workflows, the default should be “create preview and ask for approval” when the output exceeds the agent direct height limit.

### 17.17 Hardware validation for long-print support

Add a dedicated **Long Print Reliability Test** inside the printer certification wizard.

Test cases:

| Test | Purpose | Expected result |
|---|---|---|
| `long_print_low_coverage_2k` | Basic long output | All markers and END line visible |
| `long_print_low_coverage_8k` | Stress transfer duration | No cutoff; final state correct |
| `band_boundary_diagonal` | Detect gaps/overlaps between raster bands | Diagonal is continuous across seams |
| `tail_margin_final_line` | Prevent bottom cutoff | Final line visible before blank tail |
| `long_sparse_text` | Verify normal long notes | Bottom checksum prints |
| `long_qr_image_mix` | Verify raster segmentation | All markers match preview |
| `dense_controlled_bands` | Verify cooldown and safety throttling | No cut, no overheat, acceptable darkness |
| `forced_disconnect_mock` | Verify partial-output classification | No false success |
| `dropped_notification_mock` | Verify fallback completion logic | No hang; no false success |
| `slow_printer_mock` | Verify height-aware timeout | Waits long enough |
| `agent_long_requires_approval` | Agent safety | MCP cannot directly print long job by default |

Long-print test output should include visible sentinels:

```text
START LP-TEST job_...
25% marker
50% marker
75% marker
END LP-TEST checksum: 7F3A
```

The app should ask the user whether the final checksum printed. If the final marker is missing, the profile remains uncertified for long-print mode.

### 17.18 Virtual printer tests

Build a virtual printer transport that simulates:

- Limited input buffer.
- Credit-based flow control.
- No flow control.
- Delayed notifications.
- Dropped notifications.
- Duplicate notifications.
- Unknown notifications.
- Disconnect before first band.
- Disconnect mid-band.
- Disconnect at segment boundary.
- Slow final OK.
- Never-sent final OK.
- Tail drain longer than expected.
- Characteristic write size rejection.
- Successful BLE writes but simulated physical cutoff after N rows.
- Thermal cooldown required after dense bands.

Assertions:

1. The reconstructed raster equals the approved raster.
2. No row is skipped or duplicated.
3. Progress monotonically increases.
4. Failure states match the phase where failure happened.
5. The daemon never reports verified success without meeting completion criteria.
6. Agent jobs never auto-retry after partial output.
7. Diagnostics include enough information to reproduce the failure.

### 17.19 Diagnostics for cutoff issues

Every print job should store:

```json
{
  "jobId": "job_...",
  "previewId": "prev_...",
  "planId": "plan_...",
  "rasterHash": "sha256:...",
  "profileId": "seznik-minix-s1-lyin48d-gy",
  "heightDots": 5320,
  "tailBlankRowsDots": 160,
  "segmentsTotal": 28,
  "segmentsStarted": 28,
  "segmentsCompleted": 28,
  "bytesPlanned": 255360,
  "bytesWrittenToBle": 255360,
  "lastSegmentIndex": 27,
  "lastRowSent": 5319,
  "notificationsSeen": 142,
  "finalOkSeen": true,
  "disconnectSeen": false,
  "tailDrainStartedAt": "...",
  "tailDrainCompletedAt": "...",
  "completionLevel": "verified",
  "errorPhase": null,
  "error": null
}
```

Diagnostics export must include:

- Print plan JSON.
- Segment metadata.
- BLE write timing summary.
- Notification timing summary.
- Completion decision explanation.
- Finalizer command result.
- Terminal OK/status result.
- Safety report.
- Printer status/profile snapshot.
- App/daemon versions.
- OS/backend information.
- User physical-output confirmation when available.

### 17.20 Implementation acceptance criteria

Long-print support is not complete until these criteria pass:

1. A virtual printer can reconstruct a 10,000-dot-high raster from banded segments with exact hash match.
2. Simulated disconnect at every segment boundary produces the correct partial-output state.
3. Simulated final OK delay does not create a false failure before the height-aware timeout.
4. Simulated missing final OK does not create verified success.
5. The hardware certification test prints an end marker successfully on the physical printer at conservative settings.
6. The hardware test passes at least three content types: sparse text, mixed image/text, and controlled dense bands.
7. The band-boundary diagonal test shows no visible seam, gap, or overlap.
8. The final-line/tail-margin test shows the last content line before the protected blank tail.
9. Agent-originated long jobs require approval unless the user explicitly enables them.
10. The UI clearly distinguishes failed, uncertain, unverified completed, and verified completed jobs.
11. Diagnostics from a failed/cutoff job are sufficient to identify whether the failure was segmentation, transport, drain, finalizer, ACK, or physical printer behavior.


---

## 18. Local daemon API

Base URL: random localhost port.  
Auth: bearer token required.  
Format: JSON.  
Events: Server-sent events from daemon to renderer.

### 17.1 Health

```http
GET /v1/health
```

```json
{
  "ok": true,
  "version": "0.1.0",
  "profileRegistryVersion": "2026.06.04",
  "mock": false
}
```

### 17.2 Printers

```http
POST /v1/printers/scan
POST /v1/printers/connect
POST /v1/printers/disconnect
GET  /v1/printers/current
GET  /v1/printers/current/status
POST /v1/printers/current/test
```

Scan result:

```json
{
  "devices": [
    {
      "id": "ble_...",
      "name": "Seznik MiniX_0194_LE",
      "rssi": -54,
      "serviceUuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
      "support": {
        "level": "detected_unverified",
        "candidateProfileIds": ["seznik-minix-s1-lyin48d-gy"],
        "reason": "Service UUID matches; model query required."
      }
    }
  ]
}
```

### 17.3 Projects

```http
GET    /v1/projects
POST   /v1/projects
GET    /v1/projects/{projectId}
PUT    /v1/projects/{projectId}
DELETE /v1/projects/{projectId}
POST   /v1/projects/{projectId}/assets
```

### 17.4 Rendering and preview

```http
POST /v1/render/preview
GET  /v1/render/previews/{previewId}
GET  /v1/render/previews/{previewId}/image.png
GET  /v1/render/previews/{previewId}/heatmap.png
```

### 17.5 Jobs

```http
POST /v1/jobs/plan
POST /v1/jobs/print
GET  /v1/jobs
GET  /v1/jobs/{jobId}
GET  /v1/jobs/{jobId}/segments
POST /v1/jobs/{jobId}/cancel
POST /v1/jobs/{jobId}/reprint
POST /v1/jobs/{jobId}/mark-output-confirmed
```

Print requires preview binding:

```json
{
  "previewId": "prev_abc123",
  "approvalToken": "appr_...",
  "copies": 1,
  "source": "ui"
}
```

Long-job status example:

```json
{
  "jobId": "job_...",
  "state": "completed_unverified",
  "phase": "finalizing",
  "bandsSent": 18,
  "totalBands": 18,
  "rowsSent": 4360,
  "totalRows": 4360,
  "bytesSent": 209280,
  "totalBytes": 209280,
  "tailBlankRowsDots": 160,
  "completionConfidence": "data_sent_final_ack_missing",
  "requiresUserCheck": true,
  "safeActions": ["confirm_complete", "feed_paper", "reprint_from_start"]
}
```

### 17.6 Agent approvals

```http
POST /v1/agent/approvals
GET  /v1/agent/approvals/{approvalId}
POST /v1/agent/approvals/{approvalId}/approve
POST /v1/agent/approvals/{approvalId}/deny
```

### 17.7 Integrations

```http
GET  /v1/integrations
POST /v1/integrations/config/preview
POST /v1/integrations/config/install
POST /v1/integrations/config/uninstall
```

### 17.8 Diagnostics

```http
POST /v1/diagnostics/export
POST /v1/diagnostics/hardware-test
GET  /v1/logs/recent
```

---

## 19. MCP design

### 18.1 MCP server type

Default: stdio MCP server.

Optional later: Streamable HTTP endpoint bound only to `127.0.0.1`, with auth and Origin validation. Do not expose network-accessible MCP in v1.

### 18.2 MCP tool design principles

- Tools should be semantic, not raw.
- No raw BLE tools in MCP.
- No firmware tools in MCP.
- Image printing requires preview and approval unless the user explicitly enables it.
- Every tool returns structured content.
- Every print-related response includes safety metrics.
- Every direct print is logged with source app, tool name, input hash, output hash, and decision.

### 18.3 MCP tools v1

```text
get_printer_status
scan_printers
connect_printer
list_supported_profiles
list_templates
render_preview
print_note
print_task_card
print_qr_label
print_markdown_preview
submit_approved_print
get_job_status
open_desktop_app
```

### 18.4 Tool behavior

#### `print_note`

Direct print allowed only when:

- Agent direct print is enabled.
- Printer is trusted.
- Paper mode is continuous.
- Text length is under limit.
- Height estimate is under limit.
- Coverage is safe.
- Rate limit is not exceeded.

Otherwise returns approval required.

#### `render_preview`

Always safe. Produces preview and approval ID.

#### `submit_approved_print`

Requires approval token from user/UI.

#### `scan_printers` and `connect_printer`

Allowed but should not auto-print. Connecting to a new printer never marks it trusted without test workflow.

### 18.5 Example MCP structured response

```json
{
  "status": "approval_required",
  "previewId": "prev_abc123",
  "approvalUrl": "minixprint://approval/appr_123",
  "safety": {
    "allowed": true,
    "warnings": ["high total black coverage"],
    "metrics": {
      "totalBlackCoverage": 0.38,
      "maxBandCoverage": 0.62
    }
  },
  "message": "Preview created. User approval is required before printing."
}
```

---

## 20. Agent integration support

### 19.1 Integration screen

Settings > Agent Integrations should show cards:

- Codex
- Claude Desktop
- Claude Code
- OpenCode
- Generic MCP stdio
- Advanced local HTTP MCP

Each card should show:

- Installed/not installed.
- Last tested.
- Config path.
- Copy config.
- Install config.
- Revert/uninstall.
- Test connection.
- Troubleshooting.

### 19.2 Codex config

Codex user-level config target:

```text
~/.codex/config.toml
```

Generated snippet:

```toml
[mcp_servers.minix_print]
command = "/ABSOLUTE/PATH/TO/minix-mcp"
args = []
startup_timeout_sec = 15.0
tool_timeout_sec = 120.0
```

The app should also support project-scoped config generation:

```text
<project>/.codex/config.toml
```

Only install project-scoped config after the user selects the project folder and confirms trust.

### 19.3 Claude Desktop config

Generate JSON:

```json
{
  "mcpServers": {
    "minix-print": {
      "type": "stdio",
      "command": "/ABSOLUTE/PATH/TO/minix-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

Also support a `.mcpb` package export later for Claude Desktop Extensions:

```text
MiniX Print Studio > Agent Integrations > Claude Desktop > Export .mcpb
```

### 19.4 Claude Code config

Generate CLI command:

```bash
claude mcp add --transport stdio minix-print -- /ABSOLUTE/PATH/TO/minix-mcp
```

Generate JSON command:

```bash
claude mcp add-json minix-print '{"type":"stdio","command":"/ABSOLUTE/PATH/TO/minix-mcp","args":[],"env":{}}'
```

### 19.5 OpenCode config

OpenCode local MCP config shape:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "minix-print": {
      "type": "local",
      "command": ["/ABSOLUTE/PATH/TO/minix-mcp"],
      "enabled": true,
      "timeout": 15000,
      "environment": {}
    }
  }
}
```

Likely user-level path:

```text
~/.config/opencode/opencode.jsonc
```

The app should detect common paths but always show the target file before modifying.

### 19.6 Generic MCP config

Show:

```json
{
  "type": "stdio",
  "command": "/ABSOLUTE/PATH/TO/minix-mcp",
  "args": [],
  "env": {}
}
```

Also show command-only form:

```bash
/ABSOLUTE/PATH/TO/minix-mcp
```

---

## 21. Packaging and installation

### 20.1 macOS

Target outputs:

- `.dmg` for user install.
- `.zip` optional for auto-update.
- Universal build eventually: arm64 + x64.

Requirements:

- Code signing.
- Notarization.
- Hardened runtime.
- Bluetooth usage description in app metadata.
- Sidecar daemon signed with the app.
- MCP shim installed to stable user data path.

### 20.2 Windows

Target outputs:

- NSIS installer.
- Portable build optional later.

Requirements:

- Code signing.
- Firewall not required because daemon binds to localhost only.
- BLE tested on Windows before official support label.
- App data under `%APPDATA%`.
- Logs under `%LOCALAPPDATA%` or app data logs.

### 20.3 Linux

Not first release unless needed.

Possible outputs:

- AppImage.
- `.deb`.
- `.rpm`.

Risks:

- BlueZ/D-Bus permissions.
- Bluetooth group membership.
- Desktop environment variance.
- Agent config path variance.

### 20.4 Sidecar build

Use PyInstaller for daemon and MCP sidecar.

Build per OS:

```bash
# macOS on macOS
pyinstaller daemon/pyinstaller/minixd.spec
pyinstaller mcp/pyinstaller/minix-mcp.spec

# Windows on Windows
pyinstaller daemon\pyinstaller\minixd.spec
pyinstaller mcp\pyinstaller\minix-mcp.spec
```

Do not assume one OS can build all sidecars.

### 20.5 Auto-updates

Use electron-builder/electron-updater after signing is stable.

Channels:

- `alpha`: developer builds.
- `beta`: hardware testers.
- `stable`: public release.

Auto-update should not silently change printer profiles without keeping old profiles available. Profile updates can alter safety behavior, so log profile version per job.

---

## 22. Data storage

### 21.1 macOS paths

```text
~/Library/Application Support/MiniX Print Studio/
├─ config.json
├─ runtime.json
├─ token
├─ printers.json
├─ integrations/
├─ bin/minix-mcp
├─ logs/
├─ diagnostics/
├─ previews/
└─ jobs/

~/Documents/MiniX Print Studio Projects/
└─ <project-id>/
   ├─ project.json
   ├─ assets/
   └─ exports/
```

### 21.2 Windows paths

```text
%APPDATA%\MiniX Print Studio\
%USERPROFILE%\Documents\MiniX Print Studio Projects\
```

### 21.3 Project folder

Each project:

```text
project-name.minixproj/
├─ project.json
├─ assets/
│  ├─ sha256-....png
│  └─ sha256-....jpg
├─ previews/
└─ exports/
```

A `.minixproj` can be a directory first. A zipped project package can come later.

---

## 23. Onboarding and setup flow

### 22.1 Welcome

- “Set up your MiniX printer.”
- “Create designs visually.”
- “Connect AI apps safely.”

Buttons:

- Set up printer.
- Explore with mock printer.
- Import existing project.

### 22.2 Bluetooth permission

Explain that the app needs Bluetooth only to connect to the local printer.

### 22.3 Scan

Show detected devices:

```text
Seznik MiniX_0194_LE
RSSI -54
Likely supported — model check required
```

### 22.4 Connect and verify

Show steps:

- BLE connected.
- Service discovered.
- Write characteristic found.
- Notify characteristic found.
- Model response: `S1_LYiN48D_GY`.
- Firmware: `V1.9.11`.
- Profile: Seznik MiniX S1.

### 22.5 Test print

Show preview and safety summary before the tiny test print.

After print, ask the user to confirm output.

### 22.6 Finish

Offer:

- Open blank canvas.
- Print sample note.
- Set up AI app integration.

---

## 24. Workspace UX details

### 23.1 Top bar

- Project title.
- Autosave state.
- Connected printer badge.
- Paper mode.
- Safety badge.
- Preview button.
- Print button.
- Command menu.

### 23.2 Left toolbar

- Select.
- Pan.
- Text.
- Shape.
- Image.
- QR.
- Barcode.
- Draw.
- Hand.

### 23.3 Left panels

Tabs:

- Layers.
- Templates.
- Assets.
- History.

### 23.4 Right inspector

Tabs:

- Design.
- Thermal.
- Preview.
- Safety.
- Job.

### 23.5 Preview panel

Shows:

- Grayscale draft.
- One-bit final preview.
- Pixel zoom.
- Heatmap.
- Safety metrics.
- Estimated height/paper length.
- Print button.

### 23.6 Command palette

Examples:

- “Add text.”
- “Import image.”
- “Make safer.”
- “Print preview.”
- “Scan printers.”
- “Open MCP setup.”
- “Export diagnostics.”

---

## 25. Templates

Built-in templates:

- Blank receipt.
- Quick note.
- Task card.
- Reminder.
- Daily plan.
- QR label.
- Wi-Fi QR card.
- Name tag.
- Small shipping-style label.
- Markdown snippet.
- Agent message card.

Template format should be the same document schema with parameter placeholders.

Example:

```json
{
  "templateId": "quick-note-v1",
  "title": "Quick Note",
  "parameters": {
    "title": { "type": "string", "maxLength": 80 },
    "body": { "type": "string", "maxLength": 800 }
  },
  "document": {}
}
```

MCP template tools should render through the same template engine.

---

## 26. Diagnostics and support

Diagnostics screen:

- App version.
- Daemon version.
- Profile registry version.
- Printer model/firmware.
- BLE service/characteristic discovery.
- Current safety settings.
- Recent print jobs.
- Long-print segment plans and completion decisions.
- BLE write/notification timing summary for failed or cutoff jobs.
- Recent MCP calls.
- Recent errors.
- Export bundle.

Diagnostic export must redact:

- User home path.
- Bluetooth MAC address where applicable.
- Tokens.
- Project content unless user opts in.
- Raw imported images unless user opts in.

---

## 27. Testing strategy

### 26.1 Unit tests

Frontend:

- Document schema validation.
- Canvas state reducers.
- Tool behavior.
- Shortcut mapping.
- Integration config generation.

Daemon:

- Profile matching.
- Protocol command generation.
- Raster packing.
- Dither algorithms.
- Safety metrics.
- Preview-to-print binding.
- API validation.

MCP:

- Tool schemas.
- Structured responses.
- Approval-required flows.
- Daemon unavailable flows.
- Rate-limit flows.

### 26.2 Golden tests

Maintain fixtures:

```text
fixtures/documents/
fixtures/expected-previews/
fixtures/expected-packed-raster/
fixtures/safety-reports/
```

Golden tests should verify:

- Same document produces same preview hash.
- Same document produces same packed raster hash.
- Safety report is stable.
- Migration preserves rendering.

### 26.3 Mock BLE tests

Mock device should simulate:

- Scan.
- Connect.
- Service discovery.
- Notify subscriptions.
- OK response.
- No OK timeout.
- Disconnect mid-print.
- Flow-control notifications.
- Unknown notification.
- Model/firmware response.
- Missing final OK after complete transfer.
- Disconnect mid-band.
- Disconnect between bands.
- Finalizer failure after complete raster transfer.
- Simulated physical cutoff after N rows.

### 26.4 Hardware tests

Hardware tests should be explicit and separate from CI.

Test suites:

- `read_only_identification`
- `tiny_print_continuous`
- `density_sweep_safe`
- `long_print_safe`
- `long_print_tail_margin`
- `long_print_band_boundary`
- `long_print_final_ack_timeout`
- `long_print_disconnect_mid_band`
- `agent_rate_limit`
- `disconnect_recovery`
- `gap_label_calibration`
- `black_mark_calibration`

### 26.5 Long-print reliability tests

Long-print tests are required in mock, integration, and hardware suites.

Mock tests:

- Missing final OK after all bands becomes `completed_unverified`.
- Mid-band disconnect becomes `failed_partial_output`.
- Between-band disconnect requires user check and does not auto-resume.
- Tail feed failure offers `feed-paper` and does not reprint automatically.
- Duplicate/unknown notifications are logged without corrupting state.

Hardware tests:

- Low-coverage 2k-dot strip.
- Low-coverage 8k-dot strip.
- Band-boundary diagonal strip.
- Final-line/tail-margin strip.
- Long text document from agent preview approval.

### 26.6 UI E2E tests

Use Playwright for renderer-level flows:

- First launch mock flow.
- Create project.
- Add text.
- Import image fixture.
- Generate preview.
- Safety warning appears.
- Print with mock printer.
- MCP setup copy flow.
- Integration install preview flow.

### 26.6 Security tests

- Electron renderer has no Node access.
- Preload exposes only allowed methods.
- Daemon rejects missing token.
- Daemon rejects non-local access if reachable.
- SVG sanitizer rejects scripts/remote references.
- MCP rejects raw BLE.
- Agent direct print settings default off.
- Integration installer backs up files.

---

## 28. CI/CD

### 27.1 Pull request CI

Run:

```bash
pnpm lint
pnpm typecheck
pnpm test
pytest
ruff check
mypy daemon/src mcp/src
```

Also run:

- Golden render tests.
- Mock BLE integration tests.
- MCP protocol tests.
- Config generator tests.

### 27.2 Build CI

macOS runner:

- Build renderer.
- Build daemon sidecar with PyInstaller.
- Build MCP sidecar with PyInstaller.
- Package Electron DMG.
- Sign/notarize for release builds.

Windows runner:

- Build renderer.
- Build daemon sidecar.
- Build MCP sidecar.
- Package NSIS installer.
- Sign for release builds.

### 27.3 Release checklist

Before stable release:

- All tests pass.
- Signed macOS app launches without Gatekeeper workaround.
- Windows installer launches without SmartScreen issues once signing reputation is acceptable.
- Fresh install flow passes.
- Upgrade flow passes.
- Uninstall leaves no daemon running.
- MCP config install/uninstall passes for each supported app.
- Hardware test passes on your printer.
- Diagnostics export redaction verified.

---

## 29. Implementation roadmap

### Phase 0 — Lock requirements and hardware facts

Deliverables:

- Confirm printer user-facing identity.
- Confirm actual paper width and paper types.
- Confirm target OS for first beta.
- Confirm whether background agent service is allowed.
- Confirm initial app name.

Exit criteria:

- Printer profile finalized enough for implementation.
- Project skeleton can start.

### Phase 1 — New monorepo bootstrap

Tasks:

- Create pnpm monorepo.
- Add Electron app.
- Add React/Vite renderer.
- Add shadcn/ui.
- Add Tailwind config.
- Add Python daemon package.
- Add Python MCP package.
- Add shared schema package.
- Add CI skeleton.

Exit criteria:

- `pnpm dev` opens Electron app.
- Electron starts mock daemon.
- Renderer calls `/v1/health`.

### Phase 2 — Daemon core and printer profile

Tasks:

- Port profile registry.
- Port BLE scanner.
- Port BLE transport.
- Port AiYin protocol.
- Port raster packing.
- Port safety baseline.
- Add typed service layer.
- Add mock BLE.

Exit criteria:

- Mock scan/connect/print passes.
- Hardware read-only scan/connect works on your printer.

### Phase 3 — Document model and canonical renderer

Tasks:

- Define document schema.
- Implement migrations.
- Implement Pillow renderer.
- Implement image preprocessing.
- Implement QR rendering.
- Implement one-bit preview.
- Implement preview hash and print binding.
- Implement safety report.

Exit criteria:

- Golden fixtures stable.
- Preview-to-print mismatch is impossible by API.

### Phase 4 — Canvas editor MVP

Tasks:

- Implement React Konva stage.
- Implement artboard.
- Implement pan/zoom.
- Implement select/move/resize/rotate.
- Implement text tool.
- Implement image import.
- Implement QR tool.
- Implement layers panel.
- Implement inspector.
- Implement undo/redo.
- Implement backend preview panel.

Exit criteria:

- User can create a simple design visually and print through mock printer.

### Phase 5 — Printer setup and hardware testing

Tasks:

- Build onboarding wizard.
- Build scan UI.
- Build profile confidence UI.
- Build read-only verification.
- Build tiny test print.
- Build user confirmation screen.
- Save trusted printer record.
- Export hardware diagnostics.

Exit criteria:

- Fresh user can set up your physical printer without terminal steps.

### Phase 6 — Print pipeline and long-print reliability

Tasks:

- Implement approval token binding.
- Implement `PrintPlan` schema.
- Implement raster band segmentation.
- Implement adaptive BLE stream controller.
- Implement height-aware completion timeout.
- Implement segment drain and tail-drain states.
- Implement completion levels: verified, unverified, uncertain, failed-before-output, failed-partial-output.
- Implement no-auto-retry policy after printable bytes are sent.
- Implement long-print progress events.
- Implement long-print diagnostics export.
- Implement virtual printer tests for delayed OK, missing OK, dropped notifications, buffer limits, and disconnects at every segment boundary.
- Implement hardware long-print certification with visible end marker and checksum.

Exit criteria:

- Safe preview-bound print works end-to-end.
- A 10,000-dot mock raster reconstructs exactly from segments.
- Physical long-print test on your printer prints the final end marker.
- The app never reports verified success without satisfying completion criteria.

### Phase 7 — Safety polish

Tasks:

- Add heatmap overlay.
- Add “make safer” actions.
- Add thermal budget model.
- Add cooldown queue behavior.
- Add long-print thermal pacing between bands.
- Add direct-agent policy.
- Add quiet hours/rate limits.
- Add warning copy.

Exit criteria:

- Dense/high-risk documents are blocked or require explicit mitigation.

### Phase 8 — MCP and agent integrations

Tasks:

- Implement MCP server using official SDK/FastMCP.
- Implement tools.
- Implement approval flow.
- Implement Codex config generator.
- Implement Claude Desktop config generator.
- Implement Claude Code command generator.
- Implement OpenCode config generator.
- Implement install preview/diff/backup/revert.
- Implement test connection.

Exit criteria:

- Codex, Claude, and OpenCode can call `get_printer_status` and `render_preview`.
- Direct print works only under configured safe policy.

### Phase 9 — Packaging

Tasks:

- PyInstaller daemon.
- PyInstaller MCP shim.
- electron-builder config.
- macOS DMG.
- Windows NSIS.
- Code signing.
- Notarization.
- Sidecar path resolution.
- First-run permissions.

Exit criteria:

- Fresh installer works on a clean machine.

### Phase 10 — Beta

Tasks:

- Add crash/log export.
- Add update channel.
- Add beta feedback path.
- Run hardware certification matrix.
- Test with at least two machines.
- Test reinstall/upgrade/uninstall.
- Test agent configs.

Exit criteria:

- Beta build is usable by someone who has never seen the repo.

### Phase 11 — Stable release

Tasks:

- Finalize docs.
- Record demo videos/GIFs.
- Publish installers.
- Publish support matrix.
- Publish known limitations.
- Publish profile contribution guide.

Exit criteria:

- User can install, set up printer, design, print, and connect MCP without developer help.

---

## 30. Risk register

| Risk | Impact | Mitigation |
|---|---:|---|
| BLE behavior differs across OS | High | macOS first; Windows after physical tests; mock BLE in CI |
| Printer model name is ambiguous | High | Require model/firmware query and test print confirmation |
| Agent prints too much/dense content | High | Direct print off by default; approval tokens; rate limits; coverage checks |
| Preview differs from print | High | Canonical daemon renderer; preview hash required for print |
| Electron renderer security issue | High | No Node integration; context isolation; sandbox; strict preload API |
| PyInstaller sidecar path issues | Medium | Per-OS build CI; sidecar smoke tests; runtime diagnostics |
| Text rendering differs by OS | Medium | Bundle fonts; render canonically in daemon |
| User edits app configs incorrectly | Medium | Copy config plus install preview; backups; revert |
| Unknown printer bricks/overheats | High | No generic support; no raw commands; tiny test prints only |
| Gap/black-mark paper modes unreliable | Medium | Continuous default; optional calibration and per-paper tests |
| Long print cutoff or false failure | High | Banded raster streaming; adaptive BLE pacing; tail drain; height-aware timeout; long-print hardware certification |
| Automatic retry duplicates physical output | High | Phase-aware failures; no auto-retry after printable bytes without explicit user approval |

---

## 31. First implementation tickets

1. Create new monorepo skeleton.
2. Add Electron + renderer dev flow.
3. Add shadcn/ui base layout.
4. Add daemon health endpoint.
5. Add daemon supervisor in Electron.
6. Add user data path utilities.
7. Add printer profile schema.
8. Add Seznik MiniX profile.
9. Port AiYin command builder.
10. Port raster packer and tests.
11. Add document schema package.
12. Add canonical renderer prototype.
13. Add React Konva artboard prototype.
14. Add preview API.
15. Add safety report API.
16. Add printer scan/connect UI with mock.
17. Add test print wizard.
18. Add print queue with mock.
19. Add print plan schema and raster band segmenter.
20. Add adaptive BLE stream controller.
21. Add height-aware completion and tail-drain state machine.
22. Add long-print virtual printer tests.
23. Add long-print hardware certification wizard.
24. Add MCP server skeleton.
25. Add Codex/Claude/OpenCode config generators.
26. Add integration install preview/backups.
27. Add PyInstaller specs.
28. Add electron-builder packaging.
29. Add macOS signing/notarization pipeline.
30. Add Windows packaging pipeline.

---

## 32. Clarifying questions required before implementation

### Printer identity and support

1. For the previous cutoff issue, roughly how long was the failing output: number of characters, approximate paper length, image height, or generated raster height if you have it?
2. Did cutoff happen at a consistent point, or only with image-heavy / dark / dense designs?
3. Did the physical printer stop printing while the app still waited, or did the printer continue but the app reported failure near the end?
4. Did the printer disconnect from Bluetooth, show a low-battery/LED warning, or need to be power-cycled after the failure?
5. Do you still have one of the files/designs that reproduced the cutoff? It should become a regression fixture.
6. What exact brand/model name is printed on the box, manual, bottom label, or app listing? The screenshot gives `Seznik MiniX_0194_LE` and model response `S1_LYiN48D_GY`, but I need the consumer-facing product name too.
7. What paper width does your printer use: 57 mm, 58 mm, or something else?
8. What roll/label types do you actually have right now: continuous only, gap labels, black-mark labels, adhesive labels, or multiple?
9. Does the printer have a physical feed button, status LED pattern, or mobile app that reports paper/cover/battery status?
10. Are you comfortable running a small sequence of test prints to certify density, continuous feed, and optional label modes?
11. Should the app display the supported profile as “Seznik MiniX” or as a more technical “S1_LYiN48D_GY BLE 384-dot” profile?
12. Do you want community users to submit diagnostics for new printer models, or should v1 be locked to your printer only?

### App/platform

13. Should the first packaged build be macOS-only, or macOS + Windows from day one?
14. Do you want the app to keep the print daemon alive after the window is closed so agents can still print?
15. Do you want cloud sync/accounts later, or should v1 be strictly local-only?

### Agent behavior

16. Should agents be allowed to direct-print short text notes by default after MCP setup, or should every agent print require approval until the user changes the setting?
17. Which agent app is highest priority for first-class testing: Codex, Claude Desktop, Claude Code, OpenCode, or something else?
18. Do you want the app to produce a Claude Desktop `.mcpb` extension in v1, or is copy/install config enough for v1?

### Canvas/product scope

19. For the first canvas release, which matters more: image/photo editing quality, text/layout quality, or QR/label workflows?
20. Should the canvas use a fixed-height page that users resize manually, or an auto-growing receipt strip?
21. Do you want collaboration/cloud templates later, or is this a single-user desktop tool?

---

## 33. Source URLs used for research

- Electron security: https://www.electronjs.org/docs/latest/tutorial/security
- Electron code signing: https://www.electronjs.org/docs/latest/tutorial/code-signing
- electron-builder: https://www.electron.build/
- electron-builder publish/update docs: https://www.electron.build/docs/publish
- PyInstaller docs: https://pyinstaller.org/en/stable/
- Bleak docs: https://bleak.readthedocs.io/
- Bleak `write_gatt_char` API: https://bleak.readthedocs.io/en/latest/api/client.html#bleak.BleakClient.write_gatt_char
- Bluetooth Core Specification GATT write procedures: https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-54/out/en/host/generic-attribute-profile--gatt-.html
- ESC/POS command reference used for `GS v 0` raster behavior: https://download.mikroe.com/documents/datasheets/ESC-POS_commands.pdf

- Bleak Client API/write semantics: https://bleak.readthedocs.io/en/latest/api/client.html
- Silicon Labs BLE throughput and acknowledged/unacknowledged transfer notes: https://docs.silabs.com/bluetooth/3.2/bluetooth-general-system-and-performance/throughput-with-bluetooth-low-energy-technology
- TI BLE GATT MTU guidance: https://software-dl.ti.com/simplelink/esd/simplelink_cc2640r2_sdk/3.30.00.20/exports/docs/blestack/ble_user_guide/html/ble-stack-3.x/gatt.html
- ESC/POS raster command reference example: https://sdkwiki.wizarpos.com/index.php/ESC_Commands
- Bluetooth Core GATT specification: https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-54/out/en/host/generic-attribute-profile--gatt-.html
- MCP transports specification: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- MCP tools specification: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Codex MCP docs: https://developers.openai.com/codex/mcp
- Codex config basics: https://developers.openai.com/codex/config-basic
- Claude Code MCP docs: https://code.claude.com/docs/en/mcp
- Claude Desktop local MCP/desktop extensions help: https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop
- Anthropic Desktop Extensions announcement: https://www.anthropic.com/engineering/desktop-extensions
- OpenCode MCP servers docs: https://opencode.ai/docs/mcp-servers/
- shadcn/ui Vite install: https://ui.shadcn.com/docs/installation/vite
- shadcn/ui intro: https://ui.shadcn.com/docs
- Konva docs: https://konvajs.org/docs/index.html
- React Konva transformer docs: https://konvajs.org/docs/react/Transformer.html
- Fabric.js docs: https://fabricjs.com/
- tldraw SDK docs: https://tldraw.dev/
