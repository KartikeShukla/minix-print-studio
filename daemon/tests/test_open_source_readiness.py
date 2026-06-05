from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
READINESS_SCRIPT = PROJECT_ROOT / "scripts" / "validate_open_source_readiness.py"
DOCUMENTED_GATE_COMMANDS = (
    "pnpm lint",
    "pnpm typecheck",
    "pnpm test",
    "pnpm build",
    "pnpm open-source-check",
    "pnpm source-package-check",
    "pnpm release-package-check",
    ".venv/bin/python -m ruff check daemon mcp",
    ".venv/bin/python -m mypy daemon/src mcp/src",
    ".venv/bin/python -m pytest daemon/tests mcp/tests",
)


def test_open_source_readiness_check_passes_for_repository() -> None:
    result = subprocess.run(
        [sys.executable, str(READINESS_SCRIPT)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "open-source readiness check passed"


def test_open_source_readiness_check_rejects_private_paths(tmp_path: Path) -> None:
    validator = _load_validator()
    required_file = tmp_path / "README.md"
    required_file.write_text("local path: /Users/kartike/private\n", encoding="utf-8")

    issues = validator.validate_private_path_redaction(
        root=tmp_path,
        paths=[Path("README.md")],
    )

    assert issues == ["README.md contains private path marker: /Users/"]


def test_open_source_readiness_check_requires_community_governance_docs() -> None:
    validator = _load_validator()

    assert Path("CONTRIBUTING.md") in validator.REQUIRED_FILES
    assert Path("CODE_OF_CONDUCT.md") in validator.REQUIRED_FILES


def test_open_source_readiness_check_requires_public_support_docs() -> None:
    validator = _load_validator()

    assert Path("docs/support-matrix.md") in validator.REQUIRED_DOCS
    assert Path("docs/known-limitations.md") in validator.REQUIRED_DOCS


def test_open_source_readiness_check_requires_release_notes_template() -> None:
    validator = _load_validator()

    assert Path("docs/release-notes-template.md") in validator.REQUIRED_DOCS


def test_open_source_readiness_check_requires_community_intake_templates() -> None:
    validator = _load_validator()

    assert Path(".github/PULL_REQUEST_TEMPLATE.md") in validator.REQUIRED_FILES
    assert Path(".github/ISSUE_TEMPLATE/bug_report.yml") in validator.REQUIRED_FILES
    assert Path(".github/ISSUE_TEMPLATE/feature_request.yml") in validator.REQUIRED_FILES
    assert Path(".github/ISSUE_TEMPLATE/hardware_profile.yml") in validator.REQUIRED_FILES
    assert Path(".github/ISSUE_TEMPLATE/beta_feedback.yml") in validator.REQUIRED_FILES


def test_open_source_readiness_check_requires_dependabot_config() -> None:
    validator = _load_validator()

    assert Path(".github/dependabot.yml") in validator.REQUIRED_FILES


def test_open_source_readiness_check_requires_codeql_workflow() -> None:
    validator = _load_validator()

    assert Path(".github/workflows/codeql.yml") in validator.REQUIRED_FILES


def test_open_source_readiness_check_requires_codeql_workflow_permissions() -> None:
    validator = _load_validator()

    issues = validator.validate_codeql_workflow_text(
        """
name: CodeQL
on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "21 3 * * 1"
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
jobs:
  analyze:
    if: ${{ !github.event.repository.private || vars.MINIX_ENABLE_PRIVATE_CODEQL == 'true' }}
    steps:
      - uses: github/codeql-action/init@v4
        with:
          languages: javascript-typescript, python
          queries: security-extended
      - uses: github/codeql-action/analyze@v4
"""
    )

    assert issues == [
        "CodeQL workflow must declare actions: read permissions",
        "CodeQL workflow must declare contents: read permissions",
        "CodeQL workflow must declare security-events: write permissions",
    ]


def test_open_source_readiness_check_tracks_codeql_workflow_permissions() -> None:
    validator = _load_validator()

    assert (
        ".github/workflows/codeql.yml",
        {"actions": "read", "contents": "read", "security-events": "write"},
    ) in validator.REQUIRED_WORKFLOW_PERMISSIONS.items()


def test_open_source_readiness_check_validates_codeql_workflow() -> None:
    validator = _load_validator()

    issues = validator.validate_codeql_workflow_text(
        """
name: CodeQL
permissions:
  actions: read
  contents: read
  security-events: write
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
jobs:
  analyze:
    if: ${{ !github.event.repository.private || vars.MINIX_ENABLE_PRIVATE_CODEQL == 'true' }}
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v4
        with:
          languages: javascript-typescript
      - uses: github/codeql-action/analyze@v4
"""
    )

    assert issues == [
        "CodeQL workflow missing Python analysis",
        "CodeQL workflow must run on pull requests",
        "CodeQL workflow must run on pushes to main",
        "CodeQL workflow must run on a weekly schedule",
        "CodeQL workflow must use the security-extended query suite",
    ]


def test_open_source_readiness_check_requires_codeql_private_repo_guard() -> None:
    validator = _load_validator()

    issues = validator.validate_codeql_workflow_text(
        _codeql_workflow_text().replace(
            "    if: ${{ !github.event.repository.private || "
            "vars.MINIX_ENABLE_PRIVATE_CODEQL == 'true' }}\n",
            "",
        )
    )

    assert issues == [
        "CodeQL workflow must skip private repositories unless "
        "MINIX_ENABLE_PRIVATE_CODEQL is true",
    ]


def test_open_source_readiness_check_validates_dependabot_config() -> None:
    validator = _load_validator()

    issues = validator.validate_dependabot_config_text(
        """
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
"""
    )

    assert issues == [
        "dependabot config missing github-actions updates for /",
        "dependabot config missing pip updates for /daemon",
        "dependabot config missing pip updates for /mcp",
        "dependabot config must limit open pull requests",
        "dependabot config must label update pull requests",
    ]


def test_open_source_readiness_matches_dependabot_ecosystem_directory_pairs() -> None:
    validator = _load_validator()

    issues = validator.validate_dependabot_config_text(
        """
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/mcp"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
  - package-ecosystem: "pip"
    directory: "/daemon"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
"""
    )

    assert issues == [
        "dependabot config missing npm updates for /",
        "dependabot config missing pip updates for /mcp",
    ]


def test_open_source_readiness_scans_issue_templates_for_private_paths(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    issue_template = tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
    issue_template.parent.mkdir(parents=True)
    issue_template.write_text("description: /Users/kartike/private\n", encoding="utf-8")

    assert issue_template.relative_to(tmp_path) in validator._shareable_text_paths(tmp_path)


def test_open_source_readiness_check_requires_source_package_script() -> None:
    validator = _load_validator()

    issues = validator.validate_package_scripts(
        {
            "open-source-check": (
                "node scripts/run_python.mjs scripts/validate_open_source_readiness.py"
            ),
        }
    )

    assert issues == [
        "package.json missing source-package-check script",
        "package.json missing release-package-check script",
    ]


def test_open_source_readiness_check_requires_cross_platform_python_runner() -> None:
    validator = _load_validator()

    assert validator.REQUIRED_PACKAGE_SCRIPTS["open-source-check"].startswith(
        "node scripts/run_python.mjs "
    )


def test_open_source_readiness_check_rejects_pnpm_ci_command_without_setup() -> None:
    validator = _load_validator()

    issues = validator.validate_ci_workflow(
        """
permissions:
  contents: read
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
jobs:
  python:
    steps:
      - run: python3 scripts/validate_open_source_readiness.py
      - run: pnpm source-package-check
"""
    )

    assert issues == [
        "CI missing command: pnpm release-package-check",
        "CI command requires pnpm setup before use: pnpm source-package-check",
    ]


def test_open_source_readiness_check_requires_ci_workflow_permissions() -> None:
    validator = _load_validator()

    issues = validator.validate_ci_workflow(
        """
name: CI
on:
  pull_request:
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
jobs:
  node:
    steps:
      - uses: pnpm/action-setup@v4
      - run: python3 scripts/validate_open_source_readiness.py
      - run: pnpm source-package-check
      - run: pnpm release-package-check
"""
    )

    assert issues == ["CI workflow must declare contents: read permissions"]


def test_open_source_readiness_check_rejects_write_all_workflow_permissions() -> None:
    validator = _load_validator()

    issues = validator.validate_workflow_permissions_text(
        label="release package workflow",
        text="""
permissions: write-all
jobs:
  package:
    steps:
      - run: pnpm release-package-check
""",
        required_permissions={"contents": "read"},
    )

    assert issues == [
        "release package workflow must not use write-all permissions",
        "release package workflow must declare contents: read permissions",
    ]


def test_open_source_readiness_check_requires_node24_actions_runtime_opt_in() -> None:
    validator = _load_validator()

    issues = validator.validate_workflow_node24_runtime_text(
        label="CI workflow",
        text="""
permissions:
  contents: read
jobs:
  node:
    steps:
      - uses: actions/checkout@v4
""",
    )

    assert issues == [
        "CI workflow must opt into the Node 24 JavaScript action runtime",
    ]


def test_open_source_readiness_check_requires_release_workflow_permissions() -> None:
    validator = _load_validator()

    assert (
        ".github/workflows/release-package.yml",
        {"contents": "read"},
    ) in validator.REQUIRED_WORKFLOW_PERMISSIONS.items()


def test_open_source_readiness_check_requires_documented_non_hardware_gates(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    _write_minimum_ready_repository(tmp_path, validator)
    stale_testing_doc = _gate_doc_text(DOCUMENTED_GATE_COMMANDS[:-1])
    (tmp_path / "docs" / "testing.md").write_text(stale_testing_doc, encoding="utf-8")

    issues = validator.validate_repository(tmp_path)

    assert issues == [
        "docs/testing.md missing documented gate command: "
        ".venv/bin/python -m pytest daemon/tests mcp/tests",
    ]


def _load_validator() -> object:
    spec = importlib.util.spec_from_file_location("open_source_readiness", READINESS_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_minimum_ready_repository(root: Path, validator: object) -> None:
    for relative_path in (*validator.REQUIRED_FILES, *validator.REQUIRED_DOCS):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public placeholder\n", encoding="utf-8")

    (root / ".gitignore").write_text(
        "\n".join(validator.REQUIRED_GITIGNORE_ENTRIES) + "\n",
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        json.dumps({"scripts": validator.REQUIRED_PACKAGE_SCRIPTS}),
        encoding="utf-8",
    )
    (root / ".github" / "workflows" / "ci.yml").write_text(
        _ci_workflow_text(),
        encoding="utf-8",
    )
    (root / ".github" / "workflows" / "codeql.yml").write_text(
        _codeql_workflow_text(),
        encoding="utf-8",
    )
    (root / ".github" / "workflows" / "release-package.yml").write_text(
        _release_package_workflow_text(),
        encoding="utf-8",
    )
    (root / ".github" / "dependabot.yml").write_text(
        _dependabot_config_text(),
        encoding="utf-8",
    )
    for relative_path in (
        Path("CONTRIBUTING.md"),
        Path("docs/release.md"),
        Path("docs/testing.md"),
    ):
        (root / relative_path).write_text(
            _gate_doc_text(DOCUMENTED_GATE_COMMANDS),
            encoding="utf-8",
        )


def _gate_doc_text(commands: tuple[str, ...]) -> str:
    return "Run the non-hardware gates:\n\n```bash\n" + "\n".join(commands) + "\n```\n"


def _ci_workflow_text() -> str:
    return """
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

permissions:
  contents: read
jobs:
  web:
    steps:
      - uses: pnpm/action-setup@v4
      - run: python3 scripts/validate_open_source_readiness.py
      - run: pnpm source-package-check
      - run: pnpm release-package-check
"""


def _release_package_workflow_text() -> str:
    return """
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

permissions:
  contents: read
jobs:
  package:
    steps:
      - run: pnpm release-package-check
"""


def _codeql_workflow_text() -> str:
    return """
name: CodeQL
on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "21 3 * * 1"
permissions:
  actions: read
  contents: read
  security-events: write
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
jobs:
  analyze:
    if: ${{ !github.event.repository.private || vars.MINIX_ENABLE_PRIVATE_CODEQL == 'true' }}
    steps:
      - uses: github/codeql-action/init@v4
        with:
          languages: javascript-typescript, python
          queries: security-extended
      - uses: github/codeql-action/analyze@v4
"""


def _dependabot_config_text() -> str:
    return """
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
  - package-ecosystem: "pip"
    directory: "/daemon"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
  - package-ecosystem: "pip"
    directory: "/mcp"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
"""
