from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
READINESS_SCRIPT = PROJECT_ROOT / "scripts" / "validate_open_source_readiness.py"


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


def _load_validator() -> object:
    spec = importlib.util.spec_from_file_location("open_source_readiness", READINESS_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
