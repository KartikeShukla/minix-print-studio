from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_FILES = (
    Path("README.md"),
    Path("LICENSE"),
    Path("SECURITY.md"),
    Path("CONTRIBUTING.md"),
    Path("CODE_OF_CONDUCT.md"),
    Path(".gitignore"),
    Path("package.json"),
    Path("pnpm-workspace.yaml"),
    Path("turbo.json"),
    Path(".github/dependabot.yml"),
    Path(".github/workflows/ci.yml"),
    Path(".github/workflows/release-package.yml"),
    Path(".github/PULL_REQUEST_TEMPLATE.md"),
    Path(".github/ISSUE_TEMPLATE/bug_report.yml"),
    Path(".github/ISSUE_TEMPLATE/feature_request.yml"),
    Path(".github/ISSUE_TEMPLATE/hardware_profile.yml"),
)

REQUIRED_DOCS = (
    Path("docs/architecture.md"),
    Path("docs/printer-profiles.md"),
    Path("docs/hardware-certification.md"),
    Path("docs/mcp-integrations.md"),
    Path("docs/safety.md"),
    Path("docs/release.md"),
    Path("docs/release-notes-template.md"),
    Path("docs/support-matrix.md"),
    Path("docs/known-limitations.md"),
    Path("docs/testing.md"),
    Path("docs/troubleshooting.md"),
)

REQUIRED_GITIGNORE_ENTRIES = (
    ".env",
    ".env.*",
    "node_modules/",
    ".venv/",
    "runtime/",
    "logs/",
    "diagnostics/",
    "previews/",
    "jobs/",
)

PRIVATE_PATH_MARKERS = (
    "/Users/",
    "/home/",
    "C:\\Users\\",
)

SHAREABLE_TEXT_GLOBS = (
    "*.md",
    ".github/*.yml",
    ".github/*.md",
    ".github/workflows/*.yml",
    ".github/ISSUE_TEMPLATE/*.yml",
    "docs/*.md",
    "profiles/**/*.json",
    "scripts/*.sh",
)

REQUIRED_PACKAGE_SCRIPTS = {
    "open-source-check": "node scripts/run_python.mjs scripts/validate_open_source_readiness.py",
    "source-package-check": "node scripts/run_python.mjs scripts/validate_source_package.py",
    "release-package-check": "node scripts/run_python.mjs scripts/validate_release_packaging.py",
}

REQUIRED_NON_HARDWARE_GATE_COMMANDS = (
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

REQUIRED_GATE_DOCS = (
    Path("CONTRIBUTING.md"),
    Path("docs/release.md"),
    Path("docs/testing.md"),
)

REQUIRED_DEPENDABOT_BLOCKS = (
    ("npm", "/"),
    ("github-actions", "/"),
    ("pip", "/daemon"),
    ("pip", "/mcp"),
)


def main() -> int:
    root = Path.cwd()
    issues = validate_repository(root)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("open-source readiness check passed")
    return 0


def validate_repository(root: Path) -> list[str]:
    issues: list[str] = []
    issues.extend(_missing_paths(root, REQUIRED_FILES))
    issues.extend(_missing_paths(root, REQUIRED_DOCS))
    issues.extend(_missing_gitignore_entries(root))
    issues.extend(_missing_package_scripts(root))
    issues.extend(_missing_ci_commands(root))
    issues.extend(_dependabot_config_issues(root))
    issues.extend(_missing_documented_gate_commands(root))
    issues.extend(validate_private_path_redaction(root=root, paths=_shareable_text_paths(root)))
    return issues


def validate_private_path_redaction(*, root: Path, paths: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in paths:
        text = (root / path).read_text(encoding="utf-8")
        for marker in PRIVATE_PATH_MARKERS:
            if marker in text:
                issues.append(f"{path.as_posix()} contains private path marker: {marker}")
                break
    return issues


def _missing_paths(root: Path, paths: tuple[Path, ...]) -> list[str]:
    return [f"missing required file: {path.as_posix()}" for path in paths if not (root / path).is_file()]


def _missing_gitignore_entries(root: Path) -> list[str]:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return ["missing required file: .gitignore"]
    entries = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    return [
        f"missing .gitignore entry: {entry}"
        for entry in REQUIRED_GITIGNORE_ENTRIES
        if entry not in entries
    ]


def _missing_package_scripts(root: Path) -> list[str]:
    package_json = root / "package.json"
    if not package_json.is_file():
        return ["missing required file: package.json"]
    payload = json.loads(package_json.read_text(encoding="utf-8"))
    scripts = payload.get("scripts")
    if not isinstance(scripts, dict):
        return ["package.json missing scripts object"]
    return validate_package_scripts(scripts)


def validate_package_scripts(scripts: dict[str, object]) -> list[str]:
    issues: list[str] = []
    for script_name, command in REQUIRED_PACKAGE_SCRIPTS.items():
        if scripts.get(script_name) != command:
            issues.append(f"package.json missing {script_name} script")
    return issues


def _missing_ci_commands(root: Path) -> list[str]:
    workflow = root / ".github" / "workflows" / "ci.yml"
    if not workflow.is_file():
        return ["missing required file: .github/workflows/ci.yml"]
    text = workflow.read_text(encoding="utf-8")
    return validate_ci_workflow(text)


def _missing_documented_gate_commands(root: Path) -> list[str]:
    issues: list[str] = []
    for relative_path in REQUIRED_GATE_DOCS:
        path = root / relative_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for command in REQUIRED_NON_HARDWARE_GATE_COMMANDS:
            if command not in text:
                issues.append(
                    f"{relative_path.as_posix()} missing documented gate command: {command}"
                )
    return issues


def validate_ci_workflow(text: str) -> list[str]:
    issues: list[str] = []
    required_commands = (
        "python3 scripts/validate_open_source_readiness.py",
        "pnpm source-package-check",
        "pnpm release-package-check",
    )
    issues.extend(
        f"CI missing command: {command}" for command in required_commands if command not in text
    )
    issues.extend(_pnpm_setup_issues(text))
    return issues


def validate_dependabot_config_text(text: str) -> list[str]:
    issues: list[str] = []
    update_blocks = _dependabot_update_blocks(text)
    for ecosystem, directory in REQUIRED_DEPENDABOT_BLOCKS:
        if not _dependabot_block_exists(update_blocks, ecosystem, directory):
            issues.append(f"dependabot config missing {ecosystem} updates for {directory}")
    if "open-pull-requests-limit:" not in text:
        issues.append("dependabot config must limit open pull requests")
    if "labels:" not in text or "dependencies" not in text:
        issues.append("dependabot config must label update pull requests")
    return issues


def _dependabot_config_issues(root: Path) -> list[str]:
    dependabot_config = root / ".github" / "dependabot.yml"
    if not dependabot_config.is_file():
        return ["missing required file: .github/dependabot.yml"]
    return validate_dependabot_config_text(dependabot_config.read_text(encoding="utf-8"))


def _dependabot_update_blocks(text: str) -> list[str]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("- package-ecosystem:"):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(block) for block in blocks]


def _dependabot_block_exists(blocks: list[str], ecosystem: str, directory: str) -> bool:
    return any(
        f'package-ecosystem: "{ecosystem}"' in block
        and f'directory: "{directory}"' in block
        and 'interval: "weekly"' in block
        for block in blocks
    )


def _pnpm_setup_issues(text: str) -> list[str]:
    issues: list[str] = []
    pnpm_setup_seen = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if _is_workflow_job_header(line):
            pnpm_setup_seen = False
            continue
        if "pnpm/action-setup" in stripped:
            pnpm_setup_seen = True
        if stripped.startswith("- run: pnpm ") and not pnpm_setup_seen:
            command = stripped.removeprefix("- run: ")
            issues.append(f"CI command requires pnpm setup before use: {command}")
    return issues


def _is_workflow_job_header(line: str) -> bool:
    return line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":")


def _shareable_text_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for pattern in SHAREABLE_TEXT_GLOBS:
        for path in root.glob(pattern):
            if path.is_file():
                paths.add(path.relative_to(root))
    return sorted(paths)


if __name__ == "__main__":
    raise SystemExit(main())
