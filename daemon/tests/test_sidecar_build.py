from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build_sidecars.py"


def test_sidecar_build_plan_uses_pyinstaller_onefile_outputs() -> None:
    builder = _load_builder()

    plan = builder.build_sidecar_plan(
        root=PROJECT_ROOT,
        python_executable="/repo/.venv/bin/python",
        platform="darwin",
    )

    assert [command.name for command in plan.commands] == ["minixd", "minix-mcp"]
    assert plan.output_dir == PROJECT_ROOT / "dist" / "sidecars"
    assert plan.pyinstaller_config_dir == PROJECT_ROOT / "build" / "pyinstaller" / "config"
    assert all(
        command.args[:3] == ["/repo/.venv/bin/python", "-m", "PyInstaller"]
        for command in plan.commands
    )
    assert all("--onefile" in command.args for command in plan.commands)
    assert all("--noconfirm" in command.args for command in plan.commands)
    assert all(
        str(PROJECT_ROOT / "dist" / "sidecars") in command.args
        for command in plan.commands
    )
    assert plan.expected_binaries == [
        PROJECT_ROOT / "dist" / "sidecars" / "minixd",
        PROJECT_ROOT / "dist" / "sidecars" / "minix-mcp",
    ]


def test_daemon_sidecar_bundles_profile_data() -> None:
    builder = _load_builder()

    plan = builder.build_sidecar_plan(
        root=PROJECT_ROOT,
        python_executable="/repo/.venv/bin/python",
        platform="darwin",
    )

    minixd_command = next(command for command in plan.commands if command.name == "minixd")
    add_data_index = minixd_command.args.index("--add-data")

    assert (
        minixd_command.args[add_data_index + 1]
        == f"{PROJECT_ROOT / 'profiles'}:profiles"
    )


def test_sidecar_build_prefers_repo_virtualenv_python(tmp_path: Path) -> None:
    builder = _load_builder()
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\n", encoding="utf-8")

    assert builder.default_python_executable(tmp_path, platform="darwin") == str(venv_python)


def test_sidecar_build_rejects_cross_platform_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _load_builder()
    monkeypatch.setattr(builder.sys, "platform", "darwin")

    with pytest.raises(SystemExit) as exc_info:
        builder.main(["--target-platform", "win32"])

    assert exc_info.value.code == 2


def _load_builder() -> object:
    assert SIDECAR_BUILD_SCRIPT.is_file(), "missing sidecar build script"
    spec = importlib.util.spec_from_file_location("sidecar_build", SIDECAR_BUILD_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
