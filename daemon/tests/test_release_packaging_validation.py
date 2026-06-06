from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_PACKAGING_SCRIPT = PROJECT_ROOT / "scripts" / "validate_release_packaging.py"
BLUETOOTH_USAGE_DESCRIPTION = (
    "MiniX Print Studio uses Bluetooth only to connect to your local "
    "MiniX thermal printer."
)
BLUETOOTH_EXTEND_INFO = (
    "  extendInfo:\n"
    f"    NSBluetoothAlwaysUsageDescription: {BLUETOOTH_USAGE_DESCRIPTION}\n"
    f"    NSBluetoothPeripheralUsageDescription: {BLUETOOTH_USAGE_DESCRIPTION}\n"
)


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
        "package.json missing package:win-installer script",
        "apps/desktop/package.json missing package:mac script",
        "apps/desktop/package.json missing package:win script",
        "apps/desktop/package.json missing package:win-installer script",
    ]


def test_release_packaging_check_requires_cross_platform_python_runner() -> None:
    validator = _load_validator()

    assert validator.ROOT_REQUIRED_PACKAGE_SCRIPTS["build:sidecars"].startswith(
        "node scripts/run_python.mjs "
    )


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
            "package:win-installer": validator.DESKTOP_REQUIRED_PACKAGE_SCRIPTS[
                "package:win-installer"
            ],
        },
    )

    assert issues == ["apps/desktop/package.json missing package:win script"]


def test_release_packaging_check_requires_windows_installer_package_command() -> None:
    validator = _load_validator()

    issues = validator.validate_package_scripts(
        root_scripts={
            **validator.ROOT_REQUIRED_PACKAGE_SCRIPTS,
            "package:win-installer": "pnpm --filter @minix/desktop package:win",
        },
        desktop_scripts={
            **validator.DESKTOP_REQUIRED_PACKAGE_SCRIPTS,
            "package:win-installer": validator.DESKTOP_REQUIRED_PACKAGE_SCRIPTS[
                "package:win"
            ],
        },
    )

    assert issues == [
        "package.json missing package:win-installer script",
        "apps/desktop/package.json missing package:win-installer script",
    ]


def test_release_packaging_check_requires_desktop_integration_configs_source_alias() -> None:
    validator = _load_validator()

    issues = validator.validate_desktop_tsconfig_text(
        """
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {}
  }
}
"""
    )

    assert issues == [
        "apps/desktop/tsconfig.json must map @minix/integration-configs to source",
    ]


def test_release_packaging_check_requires_windows_package_workflow() -> None:
    validator = _load_validator()

    issues = validator.validate_release_package_workflow_text(
        _complete_release_workflow_text()
        .replace("          - os: windows-latest\n", "")
        .replace(
            "            artifact_name: minix-print-studio-windows-installer-unsigned\n",
            "",
        )
        .replace("      - run: pnpm package:win\n", "")
        .replace("      - run: pnpm package:win-installer\n", "")
    )

    assert issues == [
        "release package workflow missing Windows runner",
        "release package workflow missing command: pnpm package:win",
        "release package workflow missing command: pnpm package:win-installer",
        "release package workflow missing Windows unsigned installer artifact name",
    ]


def test_release_packaging_check_requires_manual_release_package_dispatch() -> None:
    validator = _load_validator()

    issues = validator.validate_release_package_workflow_text(
        _complete_release_workflow_text().replace("  workflow_dispatch:\n", "")
    )

    assert issues == ["release package workflow must support manual workflow_dispatch"]


def test_release_packaging_check_requires_artifact_upload_step() -> None:
    validator = _load_validator()

    issues = validator.validate_release_package_workflow_text(
        _complete_release_workflow_text().replace(
            "      - uses: actions/upload-artifact@v4\n",
            "",
        )
    )

    assert issues == ["release package workflow missing artifact upload step"]


def test_release_packaging_check_requires_platform_named_artifacts() -> None:
    validator = _load_validator()

    issues = validator.validate_release_package_workflow_text(
        _complete_release_workflow_text()
        .replace("minix-print-studio-macos-unsigned", "minix-print-studio-unsigned")
        .replace("minix-print-studio-windows-unsigned", "minix-print-studio-unsigned")
        .replace(
            "minix-print-studio-windows-installer-unsigned",
            "minix-print-studio-unsigned",
        )
    )

    assert issues == [
        "release package workflow missing macOS unsigned artifact name",
        "release package workflow missing Windows unsigned artifact name",
        "release package workflow missing Windows unsigned installer artifact name",
    ]


def test_release_packaging_check_requires_sidecar_resources() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        f"""
files:
  - out/**
mac:
  icon: build/icon.png
{BLUETOOTH_EXTEND_INFO}\
win:
  icon: build/icon.ico
  signAndEditExecutable: false
publish: null
"""
    )

    assert issues == ["electron-builder config must include sidecar binaries"]


def test_release_packaging_check_requires_macos_bluetooth_usage_descriptions() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        """
files:
  - out/**
extraResources:
  - from: ../../dist/sidecars
    to: sidecars
mac:
  icon: build/icon.png
  identity: null
win:
  icon: build/icon.ico
  signAndEditExecutable: false
publish: null
"""
    )

    assert issues == ["electron-builder config must set macOS Bluetooth usage descriptions"]


def test_release_packaging_check_rejects_runtime_state_and_signing_identity() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        f"""
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
  icon: build/icon.png
{BLUETOOTH_EXTEND_INFO}\
  identity: Developer ID Application: Example Person
win:
  icon: build/icon.ico
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
        f"""
files:
  - out/**
  - hardware-artifacts/**
extraResources:
  - from: ../../dist/sidecars
    to: sidecars
mac:
  icon: build/icon.png
{BLUETOOTH_EXTEND_INFO}\
win:
  icon: build/icon.ico
  signAndEditExecutable: false
publish: null
"""
    )

    assert issues == ["electron-builder config must exclude hardware-artifacts/"]


def test_release_packaging_check_requires_windows_resource_editing_disabled() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        f"""
win:
  target:
    - target: dir
      arch:
        - x64
extraResources:
  - from: ../../dist/sidecars
    to: sidecars
mac:
  icon: build/icon.png
{BLUETOOTH_EXTEND_INFO}\
win:
  icon: build/icon.ico
publish: null
"""
    )

    assert issues == [
        "electron-builder config must disable Windows executable resource editing",
    ]


def test_release_packaging_check_requires_explicit_package_icons() -> None:
    validator = _load_validator()

    issues = validator.validate_builder_config_text(
        f"""
files:
  - out/**
extraResources:
  - from: ../../dist/sidecars
    to: sidecars
mac:
  identity: null
{BLUETOOTH_EXTEND_INFO}\
win:
  signAndEditExecutable: false
publish: null
"""
    )

    assert issues == [
        "electron-builder config must set mac icon: build/icon.png",
        "electron-builder config must set Windows icon: build/icon.ico",
    ]


def test_release_packaging_check_requires_checksum_manifest_workflow_step() -> None:
    validator = _load_validator()

    issues = validator.validate_release_package_workflow_text(
        _complete_release_workflow_text().replace(
            "      - run: node scripts/run_python.mjs scripts/write_release_checksums.py "
            "dist/release\n",
            "",
        )
    )

    assert issues == [
        "release package workflow missing command: "
        "node scripts/run_python.mjs scripts/write_release_checksums.py dist/release",
    ]


def test_release_packaging_check_requires_artifact_upload_exclusions() -> None:
    validator = _load_validator()

    issues = validator.validate_release_package_workflow_text(
        _complete_release_workflow_text()
        .replace("          path: |\n            dist/release\n", "          path: dist/release\n")
        .replace("            !dist/release/builder-debug.yml\n", "")
        .replace("            !dist/release/.icon-*\n", "")
    )

    assert issues == [
        "release package workflow must exclude electron-builder scratch artifacts",
    ]


def test_release_packaging_check_requires_node24_actions_runtime_opt_in() -> None:
    validator = _load_validator()

    issues = validator.validate_release_package_workflow_text(
        _complete_release_workflow_text().replace(
            "env:\n  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true\n\n",
            "",
        )
    )

    assert issues == [
        "release package workflow must opt into the Node 24 JavaScript action runtime",
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


def _complete_release_workflow_text() -> str:
    return """
name: Release Package

on:
  workflow_dispatch:

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  package:
    strategy:
      matrix:
        include:
          - os: macos-latest
            artifact_name: minix-print-studio-macos-unsigned
          - os: windows-latest
            artifact_name: minix-print-studio-windows-unsigned
          - os: windows-latest
            artifact_name: minix-print-studio-windows-installer-unsigned
    steps:
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
      - uses: actions/setup-python@v5
      - run: pnpm install --frozen-lockfile
      - run: python -m pip install -e daemon[dev] -e mcp[dev]
      - run: pnpm release-package-check
      - run: pnpm package:mac
      - run: pnpm package:win
      - run: pnpm package:win-installer
      - run: node scripts/run_python.mjs scripts/write_release_checksums.py dist/release
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact_name }}
          path: |
            dist/release
            !dist/release/builder-debug.yml
            !dist/release/.icon-*
"""
