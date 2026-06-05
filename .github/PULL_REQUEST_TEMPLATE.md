## Summary

Describe the change and the user-facing workflow it improves.

## Validation

- [ ] `pnpm lint`
- [ ] `pnpm typecheck`
- [ ] `pnpm test`
- [ ] `pnpm build`
- [ ] `pnpm open-source-check`
- [ ] `pnpm source-package-check`
- [ ] `pnpm release-package-check`
- [ ] `.venv/bin/python -m ruff check daemon mcp scripts`
- [ ] `.venv/bin/python -m mypy daemon/src mcp/src`
- [ ] `.venv/bin/python -m pytest daemon/tests mcp/tests`

## Safety And Privacy

- [ ] No runtime state, tokens, logs, diagnostics exports, hardware artifacts, or private paths are committed.
- [ ] BLE ownership remains inside the daemon; Electron, MCP, and CLI paths call daemon APIs.
- [ ] Hardware behavior changes include staged certification evidence or remain mock-only.

## Release Notes

- [ ] Public docs, support matrix, known limitations, or release notes were updated when behavior changed.
