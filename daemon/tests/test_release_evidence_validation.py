from __future__ import annotations

import hashlib
import importlib.util
import json
import plistlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_EVIDENCE_SCRIPT = PROJECT_ROOT / "scripts" / "validate_release_evidence.py"


def test_release_evidence_check_accepts_successful_platform_artifacts(tmp_path: Path) -> None:
    validator = _load_validator()
    evidence_dir = tmp_path / "release-evidence"
    _write_workflow_run_json(evidence_dir / "workflow-run.json", conclusion="success")
    _write_mac_artifact(evidence_dir / "minix-print-studio-macos-unsigned")
    _write_windows_artifact(evidence_dir / "minix-print-studio-windows-unsigned")
    _write_windows_installer_artifact(
        evidence_dir / "minix-print-studio-windows-installer-unsigned"
    )

    issues = validator.validate_release_evidence(
        evidence_dir,
        workflow_run_json=evidence_dir / "workflow-run.json",
    )

    assert issues == []


def test_release_evidence_check_requires_windows_installer_artifact(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    evidence_dir = tmp_path / "release-evidence"
    _write_workflow_run_json(evidence_dir / "workflow-run.json", conclusion="success")
    _write_mac_artifact(evidence_dir / "minix-print-studio-macos-unsigned")
    _write_windows_artifact(evidence_dir / "minix-print-studio-windows-unsigned")

    issues = validator.validate_release_evidence(
        evidence_dir,
        workflow_run_json=evidence_dir / "workflow-run.json",
    )

    assert issues == [
        "missing Windows installer artifact directory: "
        "minix-print-studio-windows-installer-unsigned"
    ]


def test_release_evidence_check_requires_windows_package_and_sidecars(tmp_path: Path) -> None:
    validator = _load_validator()
    evidence_dir = tmp_path / "release-evidence"
    _write_workflow_run_json(evidence_dir / "workflow-run.json", conclusion="success")
    _write_mac_artifact(evidence_dir / "minix-print-studio-macos-unsigned")
    _write_windows_artifact(
        evidence_dir / "minix-print-studio-windows-unsigned",
        include_app_exe=False,
        include_mcp_sidecar=False,
    )
    _write_windows_installer_artifact(
        evidence_dir / "minix-print-studio-windows-installer-unsigned"
    )

    issues = validator.validate_release_evidence(
        evidence_dir,
        workflow_run_json=evidence_dir / "workflow-run.json",
    )

    assert issues == [
        "Windows artifact missing win-unpacked/MiniX Print Studio.exe",
        "Windows artifact missing win-unpacked/resources/sidecars/minix-mcp.exe",
        "Windows checksum manifest missing win-unpacked/MiniX Print Studio.exe",
        "Windows checksum manifest missing win-unpacked/resources/sidecars/minix-mcp.exe",
    ]


def test_release_evidence_check_requires_macos_bluetooth_usage_descriptions(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    mac_dir = tmp_path / "minix-print-studio-macos-unsigned"
    _write_mac_artifact(mac_dir, include_bluetooth_usage=False)

    issues = validator.validate_macos_artifact(mac_dir)

    assert issues == ["macOS artifact Info.plist missing Bluetooth usage descriptions"]


def test_release_evidence_check_rejects_failed_run_and_forbidden_artifacts(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    evidence_dir = tmp_path / "release-evidence"
    _write_workflow_run_json(evidence_dir / "workflow-run.json", conclusion="failure")
    _write_mac_artifact(evidence_dir / "minix-print-studio-macos-unsigned")
    windows_dir = evidence_dir / "minix-print-studio-windows-unsigned"
    _write_windows_artifact(windows_dir)
    _write_windows_installer_artifact(
        evidence_dir / "minix-print-studio-windows-installer-unsigned"
    )
    (windows_dir / "builder-debug.yml").write_text("debug", encoding="utf-8")
    (windows_dir / ".icon-ico" / "icon.ico").parent.mkdir(parents=True)
    (windows_dir / ".icon-ico" / "icon.ico").write_text("cache", encoding="utf-8")
    (windows_dir / "runtime" / "token").parent.mkdir(parents=True)
    (windows_dir / "runtime" / "token").write_text("secret-token", encoding="utf-8")

    issues = validator.validate_release_evidence(
        evidence_dir,
        workflow_run_json=evidence_dir / "workflow-run.json",
    )

    assert issues == [
        "workflow run conclusion is failure, expected success",
        "Windows artifact must not include builder-debug.yml",
        "Windows artifact must not include .icon-* scratch directories",
        "Windows artifact must not include runtime/",
    ]


def _load_validator() -> object:
    spec = importlib.util.spec_from_file_location(
        "release_evidence_validation",
        RELEASE_EVIDENCE_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_workflow_run_json(path: Path, *, conclusion: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": "Release Package",
                "event": "workflow_dispatch",
                "conclusion": conclusion,
                "headBranch": "codex/bootstrap-minix-print-studio",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_mac_artifact(path: Path, *, include_bluetooth_usage: bool = True) -> None:
    info_plist: dict[str, object] = {
        "CFBundleName": "MiniX Print Studio",
    }
    if include_bluetooth_usage:
        info_plist.update(
            {
                "NSBluetoothAlwaysUsageDescription": (
                    "MiniX Print Studio uses Bluetooth only to connect to your "
                    "local MiniX thermal printer."
                ),
                "NSBluetoothPeripheralUsageDescription": (
                    "MiniX Print Studio uses Bluetooth only to connect to your "
                    "local MiniX thermal printer."
                ),
            }
        )
    files = {
        "mac-arm64/MiniX Print Studio.app/Contents/Info.plist": plistlib.dumps(info_plist),
        "mac-arm64/MiniX Print Studio.app/Contents/Resources/sidecars/minixd": b"minixd",
        "mac-arm64/MiniX Print Studio.app/Contents/Resources/sidecars/minix-mcp": b"mcp",
    }
    _write_artifact_files(path, files)


def _write_windows_artifact(
    path: Path,
    *,
    include_app_exe: bool = True,
    include_mcp_sidecar: bool = True,
) -> None:
    files = {
        "win-unpacked/resources/sidecars/minixd.exe": b"minixd.exe",
    }
    if include_app_exe:
        files["win-unpacked/MiniX Print Studio.exe"] = b"app.exe"
    if include_mcp_sidecar:
        files["win-unpacked/resources/sidecars/minix-mcp.exe"] = b"mcp.exe"
    _write_artifact_files(path, files)


def _write_windows_installer_artifact(path: Path) -> None:
    _write_artifact_files(
        path,
        {
            "MiniX Print Studio-0.1.0-win-x64.exe": b"installer.exe",
        },
    )


def _write_artifact_files(path: Path, files: dict[str, bytes]) -> None:
    for relative_path, content in files.items():
        target = path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    manifest = "\n".join(
        f"{hashlib.sha256(content).hexdigest()}  {relative_path}"
        for relative_path, content in sorted(files.items())
    )
    (path / "SHA256SUMS.txt").write_text(f"{manifest}\n", encoding="utf-8")
