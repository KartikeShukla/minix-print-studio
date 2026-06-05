from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PACKAGE_SCRIPT = PROJECT_ROOT / "scripts" / "validate_source_package.py"


def test_source_package_check_passes_for_repository() -> None:
    result = subprocess.run(
        [sys.executable, str(SOURCE_PACKAGE_SCRIPT)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "source package check passed"


def test_source_package_check_rejects_runtime_state_entries() -> None:
    validator = _load_validator()

    issues = validator.validate_source_paths(
        [
            *validator.REQUIRED_SOURCE_PATHS,
            Path("runtime/token"),
            Path("apps/desktop/out/main/index.js"),
        ]
    )

    assert issues == [
        "tracked forbidden source path: runtime/token",
        "tracked forbidden source path: apps/desktop/out/main/index.js",
    ]


def test_source_package_check_requires_release_notes_template() -> None:
    validator = _load_validator()

    assert Path("docs/release-notes-template.md") in validator.REQUIRED_SOURCE_PATHS


def test_source_package_check_requires_sidecar_build_script() -> None:
    validator = _load_validator()

    assert Path("scripts/build_sidecars.py") in validator.REQUIRED_SOURCE_PATHS


def _load_validator() -> object:
    spec = importlib.util.spec_from_file_location(
        "source_package_validation",
        SOURCE_PACKAGE_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
