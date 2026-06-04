# Architecture

MiniX Print Studio is split into explicit process and package boundaries.

## Processes

- Electron main process owns app lifecycle, menus, tray state, secure preload IPC, and daemon supervision.
- React renderer owns the visual workspace, onboarding, settings, integrations, and diagnostics UI.
- Python daemon owns BLE, printer profiles, canonical rendering, safety, preview binding, print planning, print jobs, and diagnostics.
- MCP stdio shim exposes semantic local tools and calls the daemon over localhost.

## Package Boundaries

- `apps/desktop`: Electron main and preload code.
- `apps/renderer`: React/Vite application.
- `packages/shared-api`: shared TypeScript schemas and API contracts.
- `packages/design-model`: versioned print document model.
- `packages/integration-configs`: safe MCP config generators.
- `daemon`: Python FastAPI daemon.
- `mcp`: Python stdio MCP shim.
- `profiles`: printer profile data and schema.

Printer protocol logic belongs in the daemon, not in Electron or MCP.
