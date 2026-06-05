from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REQUIRED_SOURCE_PATHS = (
    Path("README.md"),
    Path("LICENSE"),
    Path("SECURITY.md"),
    Path("CONTRIBUTING.md"),
    Path("CODE_OF_CONDUCT.md"),
    Path("package.json"),
    Path("pnpm-lock.yaml"),
    Path("pnpm-workspace.yaml"),
    Path("turbo.json"),
    Path(".github/workflows/release-package.yml"),
    Path("docs/architecture.md"),
    Path("docs/release.md"),
    Path("docs/release-notes-template.md"),
    Path("docs/support-matrix.md"),
    Path("docs/known-limitations.md"),
    Path("apps/desktop/electron-builder.yml"),
    Path("scripts/validate_release_packaging.py"),
    Path("scripts/run_python.mjs"),
    Path("scripts/build_sidecars.py"),
)

FORBIDDEN_SOURCE_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".turbo/",
    ".venv/",
    "apps/desktop/out/",
    "apps/renderer/dist/",
    "build/",
    "coverage/",
    "diagnostics/",
    "dist/",
    "jobs/",
    "logs/",
    "node_modules/",
    "out/",
    "previews/",
    "runtime/",
    "test-results/",
)

FORBIDDEN_SOURCE_NAMES = (
    ".DS_Store",
)


def main() -> int:
    root = Path.cwd()
    try:
        paths = tracked_source_paths(root)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or "failed to list tracked files", file=sys.stderr)
        return 1

    issues = validate_source_paths(paths)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("source package check passed")
    return 0


def tracked_source_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def validate_source_paths(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    path_set = set(paths)
    for required_path in REQUIRED_SOURCE_PATHS:
        if required_path not in path_set:
            issues.append(f"missing required source path: {required_path.as_posix()}")

    for path in paths:
        path_text = path.as_posix()
        if path.name in FORBIDDEN_SOURCE_NAMES or any(
            path_text == prefix.rstrip("/") or path_text.startswith(prefix)
            for prefix in FORBIDDEN_SOURCE_PREFIXES
        ):
            issues.append(f"tracked forbidden source path: {path_text}")
    return issues


if __name__ == "__main__":
    raise SystemExit(main())
