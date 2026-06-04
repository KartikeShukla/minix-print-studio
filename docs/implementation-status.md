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

## Next Implementation Slices

1. Physical hardware validation for read-only model/firmware probing on the printer.
2. Canvas editor MVP depth: transformer handles, inline text editing, and pan/zoom.
3. Persisted job history and diagnostics export.
4. MCP runtime config handoff from Electron user data.
