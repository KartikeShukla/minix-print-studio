# Contributing

MiniX Print Studio welcomes focused contributions that keep printer safety, local-first
privacy, and shareable project hygiene intact.

## Development Setup

```bash
pnpm install
.venv/bin/python -m pip install -e daemon[dev] -e mcp[dev]
```

Run the desktop app during development:

```bash
pnpm dev
```

## Development Practice

- Use TDD for behavior changes: write the failing test first, make it pass, then refactor.
- Keep commits focused and reviewable.
- Do not commit runtime state, logs, diagnostics exports, hardware artifacts, local tokens, or private file paths.
- Keep BLE ownership inside the daemon. Electron, MCP, and CLI flows should call daemon APIs rather than opening direct BLE sessions.
- Hardware tests must stay explicit and separate from CI.
- Use the GitHub issue templates for bugs, feature requests, and hardware profile evidence so triage preserves reproduction steps, safety state, and redaction checks.
- Use the pull request template and fill in the validation and safety checklist before review.
- Dependabot tracks npm workspace, GitHub Actions, and Python package updates weekly. Treat those pull requests like normal code changes: review the diff, run the gates, and avoid merging updates that weaken printer safety or release packaging controls.

## Validation

Run the non-hardware gates before proposing a change:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm open-source-check
pnpm source-package-check
pnpm release-package-check
.venv/bin/python -m ruff check daemon mcp
.venv/bin/python -m mypy daemon/src mcp/src
.venv/bin/python -m pytest daemon/tests mcp/tests
```

Hardware changes also need the staged evidence described in
[docs/hardware-certification.md](docs/hardware-certification.md).

## Printer Profile Contributions

New or updated profiles must include Stage A read-only evidence, conservative defaults,
and safety limits. Redact hardware artifacts before sharing them publicly.
