# Testing

Development follows TDD for behavior code.

## Local Gates

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm open-source-check
pytest daemon/tests mcp/tests
```

## Test Layers

- Unit tests for schema validation, profile matching, config generation, protocol commands, raster packing, safety metrics, and print planning.
- Golden tests for canonical rendering and packed raster outputs.
- Mock BLE tests for scan, connect, flow control, disconnects, missing final OK, and partial-output states.
- Hardware tests are explicit and separate from CI. Stage A exports a read-only
  `hardware-test-<timestamp>.zip` artifact and must not unlock printing.
- UI E2E tests cover onboarding, mock print flow, preview, safety warnings, and integration setup.
