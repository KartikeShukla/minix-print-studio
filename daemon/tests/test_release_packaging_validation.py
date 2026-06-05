from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_PACKAGING_SCRIPT = PROJECT_ROOT / "scripts" / "validate_release_packaging.py"


def test_release_packaging_check_passes_for_repository() -> None:
    result = subprocess.run(
        [sys.executable, str(RELEASE_PACKAGING_SCRIPT)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "release packaging check passed"


def test_release_packaging_check_requires_packaging_scripts() -> None:
    validator = _load_validator()

    issues = validator.validate_package_scripts(
        root_scripts={"build": "turbo run build"},
        desktop_scripts={"build": "electron-vite build"},
    )

    assert issues == [
        "package.json missing release-package-check script",
        "package.json missing build:sidecars script",
        "package.json missing package:mac script",
        "package.json missing package:win script",
        "apps/desktop/package.json missing package:mac script",
        "apps/desktop/package.json missing package:win script",
    ]


def test_release_packaging_check_requires_windows_x64_package_command() -> None:
    validator = _load_validator()
    current_host_arch_command = (
        "pnpm build && cross-env ELECTRON_CACHE=../../dist/electron-cache "
        "ELECTRON_BUILDER_CACHE=../../dist/electron-builder-cache "
        "electron-builder --config electron-builder.yml --win --dir --publish never"
    )

    issues = validator.validate_package_scripts(
        root_scripts=validator.ROOT_REQUIRED_PACKAGE_SCRIPTS,
        desktop_scripts={
            "package:mac": validator.DESKTOP_REQUIRED_PACKAGE_SCRIPTS["package:mac"],
            "package:win": current_host_arch_command,
        },
    )

    assert issues == ["apps/desktop/package.json missing package:win script"]


def test_release_packaging_check_requires_sidecar_resources() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        """
files:
  - out/**
win:
  signAndEditExecutable: false
publish: null
"""
    )

    assert issues == ["electron-builder config must include sidecar binaries"]


def test_release_packaging_check_rejects_runtime_state_and_signing_identity() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        """
appId: app.example.private
productName: Private App
directories:
  output: ../../dist/release
files:
  - out/**
  - runtime/**
  - logs/**
extraResources:
  - from: ../../dist/sidecars
    to: sidecars
mac:
  identity: Developer ID Application: Example Person
win:
  signAndEditExecutable: false
publish:
  provider: github
"""
    )

    assert issues == [
        "electron-builder config must exclude runtime/",
        "electron-builder config must exclude logs/",
        "electron-builder config must not contain a signing identity",
        "electron-builder config must keep publishing disabled",
    ]


def test_release_packaging_check_rejects_hardware_artifact_inclusion() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        """
files:
  - out/**
  - hardware-artifacts/**
extraResources:
  - from: ../../dist/sidecars
    to: sidecars
win:
  signAndEditExecutable: false
publish: null
"""
    )

    assert issues == ["electron-builder config must exclude hardware-artifacts/"]


def test_release_packaging_check_requires_windows_resource_editing_disabled() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        """
win:
  target:
    - target: dir
      arch:
        - x64
extraResources:
  - from: ../../dist/sidecars
    to: sidecars
publish: null
"""
    )

    assert issues == [
        "electron-builder config must disable Windows executable resource editing",
    ]


def _load_validator() -> object:
    spec = importlib.util.spec_from_file_location(
        "release_packaging_validation",
        RELEASE_PACKAGING_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
