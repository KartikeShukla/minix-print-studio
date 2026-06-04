# Implementation Status

## Current Branch

`codex/bootstrap-minix-print-studio`

## Completed Checkpoints

### Bootstrap

- pnpm/Turbo monorepo.
- Electron main and preload packages.
- React/Vite renderer package.
- Python daemon package.
- Python MCP shim package.
- Shared TypeScript contracts.
- Printer profile data for `seznik-minix-s1-lyin48d-gy`.
- CI skeleton.

### Daemon Core Slice

- AiYin/LuckPrinter command builder for density, paper mode, wake, enable, raster, feed, and stop commands.
- MSB-first raster packing/unpacking helpers with coverage calculation.
- Pillow-backed canonical renderer prototype for document JSON.
- Deterministic rendering coverage for rectangle and text elements.
- Exact packed-raster test for a 384-dot document fixture.
- Print planner that appends continuous-paper tail rows and segments raster data into profile-sized bands.
- Virtual reconstruction coverage for a 10,000-dot raster.
- Preview store that binds document hash, render settings hash, raster hash, and approval token.
- `/v1/render/preview` endpoint that creates preview-bound approval artifacts.
- `/v1/render/document-preview` endpoint that renders document JSON through the daemon before creating a preview-bound approval artifact.
- `/v1/jobs/plan` endpoint that verifies the preview approval token before returning print plan and band metadata without exposing raw raster bytes.
- In-memory mock print queue that consumes preview-bound jobs and reports `completed_unverified` with user-check actions.
- `/v1/jobs/print`, `/v1/jobs`, `/v1/jobs/{jobId}`, and `/v1/jobs/{jobId}/segments` endpoints for mock print flow and job inspection.
- Renderer daemon client methods for authenticated document preview and approved print planning.
- Renderer Preview action that generates a daemon-canonical preview, plans the approved preview, surfaces preview/plan metadata, and enables Print only after plan readiness.
- Renderer daemon client method for approved preview printing through `/v1/jobs/print`.
- Renderer Print action that sends the approved preview to the mock queue and surfaces `completed_unverified`, user-check requirement, progress, and safe recovery actions.
- MCP daemon HTTP client for bearer-authenticated daemon health and document-preview requests.
- MCP core tool handlers for daemon status, document preview, and note preview flows that return approval-required responses without exposing approval tokens.
- FastMCP stdio server wrapper that registers `get_daemon_status`, `preview_document`, and `print_note` against the core MCP tool handlers.
- `minix-mcp` CLI entrypoint now runs the FastMCP stdio server instead of returning a static app-not-running response.
- Mock-first BLE discovery service that classifies profile/service/name matches as `detected_unverified` without granting print permission.
- Read-only device verification flow that matches model and firmware against the printer profile while keeping printing locked until protocol sanity testing.
- `/v1/printers/scan` endpoint with documented POST support, legacy GET smoke support, and `/v1/printers/read-only-verify` for mock adapter verification.
- Shared TypeScript API schemas for printer scan candidates and read-only verification responses.
- Renderer daemon client methods for authenticated printer scan and read-only verification.
- Renderer Scan Printers flow that displays detected candidates, runs identity verification, and shows `Printing still locked` after read-only verification.
- Bleak-backed BLE adapter for non-mock daemon mode using service-filtered advertisement discovery.
- Bleak read-only connection lifecycle with async connect/disconnect, GATT service/characteristic discovery, notify subscription, and raw notification capture.
- Profile-backed read-only model/firmware probing uses the profile's configured query commands and write characteristic while keeping printing locked until protocol sanity testing.
- Versioned document model now includes typed text elements with stable thermal defaults and immutable movement updates.
- Renderer document persistence hydrates and saves the current document through localStorage with schema validation.
- Initial React Konva artboard renders the document model, supports adding text layers from the toolbar, selects/moves text elements, and keeps the daemon preview/print state invalidated after edits.
- Renderer test harness includes a React Konva mock so canvas behavior can stay covered without depending on browser canvas support in unit tests.
- Document model now includes typed rectangle elements aligned with the daemon's canonical rectangle renderer.
- Renderer canvas can add rectangle layers, render them on the React Konva stage, show them in the layer list, and persist them with the current document.
- Renderer editor state supports undo/redo for document edits without persisting history stacks to localStorage.
- Design model exposes a generic immutable `updateElement` helper for history-aware editor mutations.
- Renderer layer list can select document elements for right-panel editing.
- Renderer inspector panel edits selected layer name, geometry, visibility, lock state, rectangle fill, and text content/fill through the persisted document history path.
- Design model now includes typed QR elements with payload and error-correction metadata.
- Daemon canonical renderer renders QR payloads into one-bit raster output and preview PNGs.
- Renderer canvas can add QR layers, display them as real QR module matrices, edit payload/error correction from the inspector, and persist them with the current document.
- Design model now includes typed embedded image elements with fit and preprocessing metadata.
- Daemon canonical renderer decodes embedded image data URLs, applies fit/threshold/invert preprocessing, and includes the result in one-bit raster output.
- Renderer image import embeds local PNG/JPEG/WebP files into the document, displays imported images on the canvas, exposes fit/threshold/invert inspector controls, and persists them with undoable document edits.
- Renderer text layers support double-click inline editing through an HTML canvas overlay that commits one undoable document edit on blur or Enter, and cancels with Escape.
- Renderer canvas footer controls zoom the artboard and Konva stage from 50% to 200% without mutating persisted print document data; inline text editing overlays scale with the zoomed canvas.
- Renderer canvas footer controls pan the stage viewport in 48-dot steps and reset to origin without mutating persisted print document data.
- Renderer selected layers show React Konva transformer handles for resize/rotate edits, persist transformed geometry through the document history path, and keep Undo available after a transform.
- Renderer completed print jobs persist to a localStorage-backed Recent Jobs list with job id, status, completion level, and band progress.
- Daemon `/v1/diagnostics/export` returns a redacted diagnostics bundle with daemon/version context, profile snapshot, job metadata, segment metadata without raw raster bytes, mock timing summaries, and completion decision explanation.
- Renderer daemon client and Recent Jobs panel can request the redacted diagnostics export and show the exported bundle job count.
- Electron writes daemon runtime handoff files under user data: `runtime/runtime.json` contains base URL, PID, start time, mock flag, and token-file path while `runtime/token` stores the bearer token separately.
- MCP integration config generators can include `MINIX_DAEMON_RUNTIME_FILE` for Codex, Claude Desktop/Code, OpenCode, and generic stdio configs without embedding bearer tokens.
- MCP stdio shim resolves daemon base URL and token from the Electron runtime handoff file, rejects inline tokens in runtime JSON, and keeps the existing explicit environment fallback for development.
- Desktop Agent Integration previews expose a stable user-data MCP shim path plus token-free config text for Codex, Claude Desktop/Code, OpenCode, and generic stdio MCP clients.
- Electron preload exposes the Agent Integration preview through IPC without passing the daemon bearer token to config snippets.
- Renderer Agent Integrations panel loads the desktop preview, shows copyable config snippets, and copies target-specific config text to the clipboard.
- Desktop Agent Integration installer writes Codex, Claude Desktop, and OpenCode configs with backup manifests before mutation; Codex uses a managed TOML block, while JSON clients preserve unrelated MCP servers.
- Desktop Agent Integration uninstall removes only the MiniX-managed config entry and can revert a mutation from its backup manifest.
- Renderer Agent Integrations panel shows install/uninstall controls only for installable targets and requires explicit confirmation before invoking the desktop installer.
- Electron materializes a stable executable `minix-mcp` shim under app user data that launches the existing Python MCP server via the repo-local MCP source path without embedding daemon tokens.
- Desktop Agent Integration connection tests verify the stable shim and runtime handoff prerequisites for a selected target.
- Renderer Agent Integrations panel exposes a non-mutating Test action and surfaces the desktop connection-test result per target.
- MCP stdio smoke helper launches the real Python MCP server against a mock daemon runtime handoff and validates daemon status without exposing daemon bearer tokens.
- Claude Desktop Agent Integration can export a token-free `.mcpb` bundle containing a manifest, local shim bridge, and install README.
- Daemon print jobs and redacted segment metadata can persist to a disk-backed JSON store and survive daemon app restarts.
- Diagnostics export supports both JSON response and downloadable ZIP archive containing redacted `diagnostics.json` plus a README.
- BLE read-only verification captures timing metadata for notify setup, notifications, writes, and notify teardown without recording raw command payloads.
- `/v1/diagnostics/hardware-test` runs Stage A read-only verification and exports a hardware-test ZIP with device/profile snapshots, BLE discovery metadata, model/firmware response files, notification/command logs, safety report, and explicit evidence that no print commands or raster bytes were sent.
- Renderer printer setup exposes `Export read-only artifact` after read-only verification so a hardware tester can capture the Stage A validation record without terminal steps.
- Non-mock BLE scan now maps host Bluetooth-unavailable failures to a structured `503` response, and the renderer daemon client preserves daemon `detail` text so the UI can show actionable setup errors.

## Current Verification

- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `pnpm build`
- `.venv/bin/python -m ruff check daemon mcp`
- `.venv/bin/python -m mypy daemon/src mcp/src`
- `.venv/bin/python -m pytest daemon/tests mcp/tests`
- Playwright smoke against `http://127.0.0.1:5173/`: add rectangle, edit inspector X/Width/fill, verify localStorage persistence.
- Playwright smoke against `http://127.0.0.1:5174/`: add QR layer, edit payload/error correction, verify localStorage persistence.
- Playwright smoke against `http://127.0.0.1:5174/`: import PNG file, verify embedded image layer and preprocessing defaults in localStorage.
- Playwright smoke against `http://127.0.0.1:5174/`: add text layer, double-click canvas text, edit the inline overlay, verify localStorage persistence and Undo enablement.
- Playwright smoke against `http://127.0.0.1:5174/`: use footer zoom controls to move 100% -> 125% -> 100% -> 75%, verify canvas width changes and localStorage remains stable.
- Playwright smoke against `http://127.0.0.1:5174/`: use footer pan controls to move 0,0 -> 48,0 -> 48,48 -> 0,0, verify reset disables and localStorage remains stable.
- Playwright smoke against `http://127.0.0.1:5174/`: add rectangle, drag the selected layer's bottom-right transformer handle, verify localStorage geometry changes from `320 x 72` to `358 x 81`.
- Playwright smoke against fresh renderer `http://127.0.0.1:5173/` and mock daemon `http://127.0.0.1:39281/`: run Preview -> Print -> Export diagnostics, verify Recent Jobs localStorage persistence and `Diagnostics exported` with `1 job in bundle`.
- TDD red/green checks for Electron runtime handoff, MCP config runtime-file env generation, and MCP shim runtime resolution.
- TDD red/green checks for desktop Agent Integration preview generation and renderer copyable Agent Integrations panel.
- TDD red/green checks for backup-first Agent Integration install/uninstall helpers and confirmation-gated renderer install controls.
- Playwright MCP smoke against `http://127.0.0.1:5173/`: Agent Integrations browser fallback renders in the right rail; daemon health fetch errors are expected in non-Electron browser mode.
- TDD red/green checks for stable MCP shim materialization, Agent Integration connection-prerequisite checks, and renderer Test action.
- TDD red/green checks for MCP stdio process smoke against a mock daemon runtime handoff.
- TDD red/green checks for Claude Desktop `.mcpb` export ZIP contents, manifest metadata, token redaction, and renderer export action.
- TDD red/green checks for disk-backed daemon job persistence, app restart job loading, and downloadable diagnostics archive contents.
- TDD red/green checks for BLE read-only timing capture in the Bleak adapter, profile probe writes, printer API serialization, and shared API parsing.
- TDD red/green checks for Stage A hardware-test ZIP export and renderer read-only artifact export action.
- TDD red/green checks for Bluetooth-unavailable scan handling across the Bleak adapter, printer API, and renderer daemon client error messages.
- Non-mock Stage A scan probe in this execution context returned `503 {"detail":"Bluetooth unavailable: Bluetooth is unsupported"}`; no physical printer validation was possible from this environment.
- Playwright MCP smoke against `http://127.0.0.1:5175/`: Agent Integrations browser fallback still renders after connection-test UI changes; daemon health fetch errors are expected in non-Electron browser mode.

## Next Implementation Slices

1. Run Stage A physical hardware validation for read-only model/firmware probing on the actual printer and inspect the exported hardware-test artifact.
2. After Stage A is confirmed on hardware, implement the protocol sanity test and tiny visual test card without unlocking trusted printing until user confirmation exists.
