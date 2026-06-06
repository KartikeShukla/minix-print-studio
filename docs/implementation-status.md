# Implementation Status

## Current Branch

Public development is on `main`; implementation slices use short-lived
`codex/*` branches and merge through reviewed pull requests.

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
- Open-source readiness validator for required public docs, ignored runtime state, CI wiring, and private-path redaction.
- Open-source readiness validator requires the README to explain project status, safety model, supported printer scope, development setup, hardware certification, agent integrations, and release validation.
- Open-source readiness validator requires public root package metadata for contributor author, GitHub repository URL, issues URL, and README homepage.
- Pre-public history validator checks git author and committer metadata for private local-host markers before the repository is made public.
- Contributor governance docs for contribution flow, conduct expectations, validation gates, and hardware-artifact redaction.
- Public support matrix and known limitations docs that distinguish mock/development support from hardware-certified support.
- Source package validator that checks the tracked release source set for required public files and forbidden runtime/build/cache paths.
- Release packaging scaffold with electron-builder config, root package commands for unsigned local macOS/Windows packages, ignored in-repo Electron build caches for restricted environments, and a validator that keeps publishing/signing disabled until release credentials exist.
- Release packaging validator rejects accidental inclusion of hardware-test artifacts alongside runtime state, diagnostics, previews, jobs, signing identity, and publishing settings.
- Windows unsigned directory packaging is pinned to x64 and disables executable resource editing so local scaffold validation does not depend on Wine code-sign/resource tools.
- Documentation gate consistency validation that keeps `CONTRIBUTING.md`, `docs/release.md`, and `docs/testing.md` aligned with the current non-hardware release checks.
- Public release notes template covering supported profiles, limitations, install/upgrade/uninstall notes, diagnostics redaction, hardware evidence, and validation checks.
- PyInstaller sidecar build script creates one-file daemon and MCP binaries under `dist/sidecars` using the repo virtualenv when available and a workspace-local PyInstaller cache.
- Daemon sidecar binaries bundle the public printer profile data and resolve profiles from `MINIX_PROFILE_ROOT`, PyInstaller's bundle root, or the source tree.
- Electron package commands build target-specific sidecars before packaging and include them as `resources/sidecars`; cross-platform sidecar builds are rejected because PyInstaller does not cross-compile.
- Release package workflow defines unsigned macOS and Windows package smokes on native GitHub Actions runners so Windows PyInstaller sidecar validation can run on Windows instead of a cross-compile path.
- Root Python-backed pnpm scripts use a cross-platform Node launcher that prefers `MINIX_PYTHON`, the repo virtualenv, then platform Python commands.
- Community intake templates cover bug reports, feature requests, hardware profile evidence, and pull requests with safety, privacy, reproduction, and validation prompts.
- Desktop package builds use tracked MiniX Print Studio icon assets instead of the default Electron icon, with a reproducible icon generator plus release/source package validators that require the macOS PNG and Windows ICO assets.
- macOS package metadata declares Bluetooth usage descriptions for local MiniX printer access, and release validators require those Info.plist keys in both source config and downloaded package evidence.
- Release package workflow writes a deterministic `SHA256SUMS.txt` manifest for uploaded unsigned package artifacts, excludes electron-builder scratch files, and validators require the checksum script and workflow step.
- Release package workflow supports manual dispatch and uploads distinct `minix-print-studio-macos-unsigned` / `minix-print-studio-windows-unsigned` evidence artifacts, with validators requiring the trigger, upload step, and artifact names.
- Release evidence validator can check a downloaded manual workflow run for successful metadata, platform-named macOS/Windows artifacts, checksum coverage, bundled sidecars, and forbidden runtime/scratch paths before making Windows release claims.
- Public GitHub repository `KartikeShukla/minix-print-studio` is live with the implementation work merged into `main`.
- Manual Release Package workflow run `27053365446` on public `main` commit `028ca71` completed successfully on macOS and Windows runners, and downloaded evidence passed `scripts/validate_release_evidence.py` with the Bluetooth usage-description gate enabled.
- Dependabot is configured for weekly npm workspace, GitHub Actions, daemon Python, and MCP Python dependency updates, with open-source/source package validators requiring the config.
- CodeQL workflow scans JavaScript/TypeScript and Python with the `security-extended` query suite on pull requests, pushes to `main`, weekly schedule, and manual dispatch.
- CodeQL, CI, and release package workflows declare explicit least-privilege GitHub token permissions, opt into GitHub's Node 24 JavaScript action runtime, and open-source readiness validation rejects missing or `write-all` workflow permissions. CodeQL includes `actions: read` for workflow-run metadata plus `security-events: write` for scan uploads, and skips while the repository is private unless `MINIX_ENABLE_PRIVATE_CODEQL=true`.

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
- Disk-backed daemon project store with `/v1/projects` create/list/get/update/delete endpoints and hash-addressed project asset upload that persist under `data_dir` when configured.
- Shared TypeScript schemas and renderer daemon client methods for project create/list/get/update/delete and hash-addressed project asset upload.
- Renderer Projects panel can load daemon project summaries, save the current document as a daemon-backed project, open saved daemon projects into the editor, update opened projects without creating duplicates, and delete projects after confirmation.
- Renderer image import uploads PNG/JPEG/WebP files to the opened daemon project's hash-addressed asset store, keeps the embedded data URL for local rendering, and persists daemon asset metadata on the document.
- Renderer startup restores the last active daemon project session before falling back to the single-document localStorage cache, and clears that remembered session when the opened project is deleted.
- Renderer shows a dismissible first-run Setup checklist that summarizes daemon, printer verification, Stage A artifact, and Agent Integration readiness without unlocking printing, and persists dismissal in localStorage.
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
- Design model can insert deterministic long-print test markers with `START LP-TEST`, 25%, 50%, 75%, and `END LP-TEST checksum: 7F3A` sentinels while preserving existing document content.
- Renderer toolbar exposes `Insert long-print test markers`, persists the 8000-dot marker fixture through the normal document history path, and keeps Undo available after insertion.
- Renderer completed print jobs persist to a localStorage-backed Recent Jobs list with job id, status, completion level, and band progress.
- Daemon `/v1/diagnostics/export` returns a redacted diagnostics bundle with daemon/version context, profile snapshot, job metadata, segment metadata without raw raster bytes, mock timing summaries, and completion decision explanation.
- Renderer daemon client and Recent Jobs panel can request the redacted diagnostics export and show the exported bundle job count.
- Electron support bundle export writes a redacted desktop ZIP under app user data with `support.json`, desktop logs, crash metadata, and a README while excluding runtime token files.
- Electron preload exposes the support bundle export through IPC, and the renderer Support panel can export the bundle and show the generated file name plus entry count.
- Electron can generate a beta feedback GitHub issue draft that includes app version, platform, timestamp, and only the support bundle file name; the renderer Support panel can copy the draft link.
- Open-source intake now includes a dedicated beta feedback issue template, and package validators require it in the tracked source set.
- Electron persists stable/beta update-channel selection under app user data and exposes it in the renderer Updates panel while keeping unsigned auto-updates disabled until signed release publishing is configured.
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
- Packaged Electron mode resolves daemon and MCP shim execution to `resources/sidecars/minixd` and `resources/sidecars/minix-mcp` instead of repo-local `.venv` and `mcp/src` paths.
- Desktop Agent Integration connection tests verify the stable shim and runtime handoff prerequisites for a selected target.
- Renderer Agent Integrations panel exposes a non-mutating Test action and surfaces the desktop connection-test result per target.
- MCP stdio smoke helper launches the real Python MCP server against a mock daemon runtime handoff and validates daemon status without exposing daemon bearer tokens.
- Claude Desktop Agent Integration can export a token-free `.mcpb` bundle containing a manifest, local shim bridge, and install README.
- Daemon print jobs and redacted segment metadata can persist to a disk-backed JSON store and survive daemon app restarts.
- Mock print jobs can simulate a segment-boundary transport disconnect and report
  `failed_partial_output` with exact bands, rows, bytes, user-check requirement,
  and no-auto-retry recovery actions after printable bytes are sent.
- Diagnostics export supports both JSON response and downloadable ZIP archive containing redacted `diagnostics.json` plus a README.
- BLE read-only verification captures timing metadata for notify setup, notifications, writes, and notify teardown without recording raw command payloads.
- `/v1/diagnostics/hardware-test` runs Stage A read-only verification and exports a hardware-test ZIP with device/profile snapshots, BLE discovery metadata, model/firmware response files, notification/command logs, safety report, and explicit evidence that no print commands or raster bytes were sent.
- Renderer printer setup exposes `Export read-only artifact` after read-only verification so a hardware tester can capture the Stage A validation record without terminal steps.
- Electron exposes an offline Stage A artifact inspector from the Printer panel that reuses the shared hardware-test CLI safety checks and shows the Stage B protocol sanity preflight without BLE writes.
- Non-mock BLE scan now maps host Bluetooth-unavailable failures to a structured `503` response, and the renderer daemon client preserves daemon `detail` text so the UI can show actionable setup errors.
- `minix-hardware-test host-readiness` reports whether the current host context exposes a Bluetooth controller before Stage A, with macOS `system_profiler SPBluetoothDataType` parsing and recommended actions for the no-controller-visible failure mode.
- Electron exposes the shared host Bluetooth readiness diagnostic and recommended actions from the Printer panel before Stage A scan attempts.
- `minix-hardware-test` and `scripts/hardware-test.sh` provide repo-local Stage A scan and read-only artifact export commands for hardware testers running against a local daemon.
- `minix-hardware-test inspect-artifact` validates exported Stage A hardware-test ZIPs offline and rejects artifacts that show print commands, raster bytes, unlocked printing, or completed certification.
- `minix-hardware-test protocol-sanity-preflight` validates a Stage A artifact and emits the deterministic Stage B wake, density, and paper-mode command plan without contacting BLE.
- `minix-hardware-test tiny-visual-card-preflight` validates a Stage A artifact and emits deterministic Stage C tiny-card metadata for `MINIX TEST 7K4P`, including dimensions, raster byte counts, and a digest without including printable bytes or contacting BLE.
- `minix-hardware-test evidence-summary` emits a redacted maintainer-shareable Stage A summary with a hashed device fingerprint, redaction flags, protocol preflight counts, and tiny-card digest without artifact paths, raw logs, command payload hex, bearer tokens, raster bytes, or the raw device id.
- Electron artifact inspection now shows the Stage B protocol sanity preflight, Stage C tiny visual card preflight, and redacted shareable evidence summary while keeping printing locked.

## Current Verification

- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `pnpm build`
- `pnpm open-source-check`
- `pnpm source-package-check`
- `pnpm release-package-check`
- `pnpm build:sidecars --target-platform darwin`
- `pnpm package:mac`
- Release package workflow contract validation for `macos-latest`, `windows-latest`, sidecar Python dependency setup, and `pnpm package:mac` / `pnpm package:win`.
- Desktop icon generation check via `.venv/bin/python scripts/generate_desktop_icons.py --check`.
- TDD red/green checks for explicit desktop package icon configuration and tracked icon assets in release/source package validation.
- TDD red/green checks for macOS Bluetooth usage descriptions in electron-builder config and downloaded release evidence.
- Unsigned macOS package smoke verified `dist/release/mac-arm64/MiniX Print Studio.app/Contents/Resources/icon.icns` and `CFBundleIconFile => icon.icns`, with no default Electron icon fallback warning.
- TDD red/green checks for release checksum manifest generation, relative CLI paths, source-package inclusion, and release workflow checksum wiring.
- TDD red/green checks for release workflow manual dispatch and platform-named artifact evidence uploads.
- TDD red/green checks for release workflow evidence validation across successful run metadata, Windows package/sidecar presence, checksum manifests, and forbidden artifact paths.
- TDD red/green checks for Dependabot config coverage across npm, GitHub Actions, daemon Python, and MCP Python dependency manifests.
- TDD red/green checks for CodeQL workflow coverage across JavaScript/TypeScript and Python plus its least-privilege scan upload permissions.
- TDD red/green checks for least-privilege GitHub Actions permissions and Node 24 JavaScript action runtime opt-in on required workflows.
- GitHub Release Package workflow run `27053365446` on public `main` commit `028ca71`: macOS unsigned package completed in 2m44s, Windows unsigned package completed in 2m56s, and downloaded artifacts passed `node scripts/run_python.mjs scripts/validate_release_evidence.py` including bundled sidecars, checksum manifests, forbidden-path exclusions, and macOS Bluetooth usage descriptions.
- Public `main` post-merge verification on merge commit `26014e5`: CI run `27054166928`, CodeQL run `27054166929`, and Release Package run `27054166927` completed successfully.
- Packaged daemon sidecar runtime smoke: `dist/release/mac-arm64/MiniX Print Studio.app/Contents/Resources/sidecars/minixd` returned `/v1/health` with mock mode and profile registry `2026.06.04`.
- `MINIX_MCP_BINARY_SMOKE="dist/release/mac-arm64/MiniX Print Studio.app/Contents/Resources/sidecars/minix-mcp" .venv/bin/python -m pytest mcp/tests/test_stdio_smoke.py::test_mcp_stdio_packaged_binary_smoke`
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
- TDD red/green checks for deterministic long-print marker generation in the shared document model and renderer toolbar insertion with persisted Undo history.
- TDD red/green checks for redacted desktop support bundle ZIP contents and the renderer Support panel export action.
- TDD red/green checks for beta feedback draft URL generation, renderer Support panel copy action, and required beta feedback issue-template packaging.
- TDD red/green checks for desktop update-channel persistence, unsupported-channel rejection, and renderer beta-channel selection.
- TDD red/green checks for Electron runtime handoff, MCP config runtime-file env generation, and MCP shim runtime resolution.
- TDD red/green checks for desktop Agent Integration preview generation and renderer copyable Agent Integrations panel.
- TDD red/green checks for backup-first Agent Integration install/uninstall helpers and confirmation-gated renderer install controls.
- Playwright MCP smoke against `http://127.0.0.1:5173/`: Agent Integrations browser fallback renders in the right rail; daemon health fetch errors are expected in non-Electron browser mode.
- TDD red/green checks for stable MCP shim materialization, Agent Integration connection-prerequisite checks, and renderer Test action.
- TDD red/green checks for packaged daemon/MCP sidecar path resolution without repo-local Python or source-path dependencies.
- TDD red/green checks for MCP stdio process smoke against a mock daemon runtime handoff.
- TDD red/green checks for Claude Desktop `.mcpb` export ZIP contents, manifest metadata, token redaction, and renderer export action.
- TDD red/green checks for disk-backed daemon job persistence, app restart job loading, and downloadable diagnostics archive contents.
- TDD red/green checks for virtual segment-boundary transport disconnects reporting
  `failed_partial_output` and diagnostics that explain why auto-retry is unsafe
  after printable bytes may have left the printer.
- TDD red/green checks for BLE read-only timing capture in the Bleak adapter, profile probe writes, printer API serialization, and shared API parsing.
- TDD red/green checks for Stage A hardware-test ZIP export and renderer read-only artifact export action.
- TDD red/green checks for Bluetooth-unavailable scan handling across the Bleak adapter, printer API, and renderer daemon client error messages.
- TDD red/green checks for host Bluetooth readiness CLI output and macOS no-controller-visible parsing.
- TDD red/green checks for the Electron host-readiness bridge and renderer Printer panel readiness result.
- TDD red/green checks for the Stage A hardware-test CLI scan/export flow and daemon error-detail preservation.
- TDD red/green checks for Stage A hardware-test artifact inspection and read-only safety rejection.
- TDD red/green checks for Stage B protocol sanity preflight planning and unsafe artifact rejection.
- TDD red/green checks for the Electron artifact-inspection bridge and renderer Stage B preflight summary from an exported Stage A artifact.
- TDD red/green checks for Stage C tiny visual card preflight planning, unsafe artifact rejection, Electron bridge propagation, and renderer checklist display.
- TDD red/green checks for redacted Stage A evidence summary generation, Electron bridge propagation, and renderer summary display.
- TDD red/green checks for open-source readiness validation and private path rejection.
- TDD red/green checks for required community README sections in open-source readiness validation.
- TDD red/green checks for required public package metadata in open-source readiness validation.
- TDD red/green checks for pre-public git history metadata validation and source package inclusion.
- TDD red/green checks for source package validation and forbidden tracked path rejection.
- TDD red/green checks for release packaging scaffold validation, including package scripts, runtime-state exclusions, disabled publishing, and absent signing identity.
- TDD red/green checks for release packaging rejection of tracked hardware-artifact includes.
- TDD red/green checks for Windows packaging x64 targeting and disabled executable resource editing.
- TDD red/green checks for PyInstaller sidecar build planning, repo-virtualenv selection, package resource inclusion, and cross-platform target rejection.
- TDD red/green checks for documented non-hardware gate consistency across contributor, release, and testing docs.
- TDD red/green checks requiring the release notes template in both open-source readiness and tracked source-package validation.
- TDD red/green checks requiring community issue and pull request templates in open-source readiness and tracked source-package validation.
- Unsigned macOS package smoke via `pnpm package:mac`; electron-builder produced `dist/release/mac-arm64` with bundled sidecars and skipped code signing because `identity` is `null`.
- Earlier unsigned Windows directory package scaffold smoke via `pnpm package:win` produced `dist/release/win-unpacked` for `arch=x64` with publishing disabled before sidecar binaries were added to the package contract. Current Windows sidecar package validation is covered by Release Package workflow run `27053365446`.
- TDD red/green checks for daemon project create/list/get/update/delete persistence and hash-addressed image asset upload across app restarts.
- TDD red/green checks for shared project API contracts and authenticated renderer project client methods.
- TDD red/green checks for the renderer Projects panel load/save/open/update/delete and daemon-backed image asset import workflows against the daemon project client.
- TDD red/green checks for renderer daemon-project session persistence, startup restore before local document cache fallback, and active-project session cleanup on delete.
- TDD red/green checks for first-run Setup checklist visibility, local dismissal persistence, and storage corruption fallback.
- Playwright MCP smoke against `http://127.0.0.1:5173/`: renderer loads after Projects/session/image-asset changes, the Image import button and Projects panel render, and the browser console only shows the React DevTools hint.
- Playwright MCP smoke against `http://127.0.0.1:5173/`: Printer panel renders the `Inspect Stage A artifact` action after the Electron artifact-inspection bridge change, and the browser console only shows the React DevTools hint.
- `scripts/hardware-test.sh --help`
- `scripts/hardware-test.sh host-readiness`
- `scripts/hardware-test.sh --help` shows `evidence-summary` as an available offline command.
- Non-mock Stage A scan attempt on 2026-06-05 against a separate daemon on `127.0.0.1:39282` returned `Bluetooth unavailable: Bluetooth is unsupported`; `system_profiler SPBluetoothDataType` reported no visible controller, so no physical printer validation was possible from this execution context even with the printer powered on.
- Playwright MCP smoke against `http://127.0.0.1:5175/`: Agent Integrations browser fallback still renders after connection-test UI changes; daemon health fetch errors are expected in non-Electron browser mode.

## Next Implementation Slices

1. Run Stage A physical hardware validation for read-only model/firmware probing on the actual printer, inspect the exported hardware-test artifact from that run, and review the protocol sanity plus tiny visual card preflight output.
2. After Stage A is confirmed on hardware, implement the physical protocol sanity executor and physical tiny visual card executor without unlocking trusted printing until user confirmation exists.
3. After Stage B and visual-card evidence exists, implement trusted-printer confirmation and keep long-print reliability as a separate certification gate.
