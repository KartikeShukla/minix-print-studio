from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_HISTORY_SCRIPT = PROJECT_ROOT / "scripts" / "validate_public_history.py"


def test_public_history_check_rejects_local_hostname_metadata() -> None:
    validator = _load_validator()

    issues = validator.validate_history_records(
        [
            validator.HistoryRecord(
                commit="b102d22",
                author_name="Kartike Shukla",
                author_email="kartike@Kartikes-MacBook-Air.local",
                committer_name="Kartike Shukla",
                committer_email="kartike@Kartikes-MacBook-Air.local",
            )
        ]
    )

    assert issues == [
        "commit b102d22 author email contains private marker: .local",
        "commit b102d22 committer email contains private marker: .local",
    ]


def test_public_history_check_allows_project_and_noreply_metadata() -> None:
    validator = _load_validator()

    issues = validator.validate_history_records(
        [
            validator.HistoryRecord(
                commit="41ba280",
                author_name="MiniX Print Studio",
                author_email="minix-print-studio@example.com",
                committer_name="MiniX Print Studio",
                committer_email="minix-print-studio@example.com",
            ),
            validator.HistoryRecord(
                commit="abcd123",
                author_name="Contributor",
                author_email="123456+contributor@users.noreply.github.com",
                committer_name="GitHub",
                committer_email="noreply@github.com",
            ),
        ]
    )

    assert issues == []


def test_public_history_check_parses_git_log_records() -> None:
    validator = _load_validator()

    records = validator.parse_history_records(
        "abc123\x00MiniX Print Studio\x00minix-print-studio@example.com"
        "\x00MiniX Print Studio\x00minix-print-studio@example.com\n"
    )

    assert records == [
        validator.HistoryRecord(
            commit="abc123",
            author_name="MiniX Print Studio",
            author_email="minix-print-studio@example.com",
            committer_name="MiniX Print Studio",
            committer_email="minix-print-studio@example.com",
        )
    ]


def test_public_history_check_passes_for_main_history() -> None:
    result = subprocess.run(
        [sys.executable, str(PUBLIC_HISTORY_SCRIPT), "HEAD..HEAD"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "public history check passed"


def _load_validator() -> object:
    spec = importlib.util.spec_from_file_location(
        "public_history_validation",
        PUBLIC_HISTORY_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
