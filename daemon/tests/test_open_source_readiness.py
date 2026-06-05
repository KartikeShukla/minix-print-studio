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


def test_open_source_readiness_check_requires_source_package_script() -> None:
    validator = _load_validator()

    issues = validator.validate_package_scripts(
        {
            "open-source-check": "python3 scripts/validate_open_source_readiness.py",
        }
    )

    assert issues == [
        "package.json missing source-package-check script",
        "package.json missing release-package-check script",
    ]


def test_open_source_readiness_check_rejects_pnpm_ci_command_without_setup() -> None:
    validator = _load_validator()

    issues = validator.validate_ci_workflow(
        """
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
jobs:
  web:
    steps:
      - uses: pnpm/action-setup@v4
      - run: python3 scripts/validate_open_source_readiness.py
      - run: pnpm source-package-check
      - run: pnpm release-package-check
"""
