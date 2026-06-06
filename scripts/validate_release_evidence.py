from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import sys
from pathlib import Path


REQUIRED_ARTIFACTS = {
    "macOS": "minix-print-studio-macos-unsigned",
    "Windows": "minix-print-studio-windows-unsigned",
    "Windows installer": "minix-print-studio-windows-installer-unsigned",
}
WINDOWS_REQUIRED_PATHS = (
    Path("win-unpacked/MiniX Print Studio.exe"),
    Path("win-unpacked/resources/sidecars/minixd.exe"),
    Path("win-unpacked/resources/sidecars/minix-mcp.exe"),
)
WINDOWS_INSTALLER_GLOB = "MiniX Print Studio-*-win-x64.exe"
FORBIDDEN_PREFIXES = (
    "runtime/",
    "logs/",
    "diagnostics/",
    "previews/",
    "jobs/",
    "hardware-artifacts/",
)
MAC_BLUETOOTH_USAGE_DESCRIPTION = (
    "MiniX Print Studio uses Bluetooth only to connect to your local MiniX thermal printer."
)
MAC_BLUETOOTH_USAGE_KEYS = (
    "NSBluetoothAlwaysUsageDescription",
    "NSBluetoothPeripheralUsageDescription",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate downloaded Release Package workflow evidence artifacts."
    )
    parser.add_argument(
        "evidence_dir",
        type=Path,
        help="Directory containing workflow-run.json and downloaded artifact directories.",
    )
    parser.add_argument(
        "--workflow-run-json",
        type=Path,
        default=None,
        help="Path to gh run view JSON. Defaults to <evidence_dir>/workflow-run.json.",
    )
    args = parser.parse_args(argv)

    issues = validate_release_evidence(
        args.evidence_dir,
        workflow_run_json=args.workflow_run_json,
    )
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("release evidence check passed")
    return 0


def validate_release_evidence(
    evidence_dir: Path,
    *,
    workflow_run_json: Path | None = None,
) -> list[str]:
    evidence_dir = evidence_dir.resolve()
    workflow_run_json = workflow_run_json or evidence_dir / "workflow-run.json"
    issues: list[str] = []

    if not evidence_dir.is_dir():
        return [f"release evidence directory does not exist: {evidence_dir}"]

    issues.extend(validate_workflow_run_json(workflow_run_json))
    issues.extend(validate_macos_artifact(evidence_dir / REQUIRED_ARTIFACTS["macOS"]))
    issues.extend(validate_windows_artifact(evidence_dir / REQUIRED_ARTIFACTS["Windows"]))
    issues.extend(
        validate_windows_installer_artifact(
            evidence_dir / REQUIRED_ARTIFACTS["Windows installer"]
        )
    )
    return issues


def validate_workflow_run_json(path: Path) -> list[str]:
    if not path.is_file():
        return [f"missing workflow run metadata: {path.name}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"workflow run metadata is not valid JSON: {exc.msg}"]

    issues: list[str] = []
    if payload.get("name") != "Release Package":
        issues.append("workflow run name is not Release Package")
    if payload.get("event") != "workflow_dispatch":
        issues.append("workflow run event is not workflow_dispatch")
    conclusion = payload.get("conclusion")
    if conclusion != "success":
        issues.append(f"workflow run conclusion is {conclusion}, expected success")
    return issues


def validate_macos_artifact(artifact_dir: Path) -> list[str]:
    issues = validate_artifact_common(artifact_dir, label="macOS")
    if issues and not artifact_dir.is_dir():
        return issues

    app_contents = find_macos_app_contents(artifact_dir)
    if app_contents is None:
        return [
            *issues,
            "macOS artifact missing MiniX Print Studio.app/Contents/Info.plist",
            "macOS artifact missing MiniX Print Studio.app/Contents/Resources/sidecars/minixd",
            "macOS artifact missing MiniX Print Studio.app/Contents/Resources/sidecars/minix-mcp",
        ]

    required_paths = (
        app_contents / "Info.plist",
        app_contents / "Resources/sidecars/minixd",
        app_contents / "Resources/sidecars/minix-mcp",
    )
    issues.extend(validate_required_paths(artifact_dir, "macOS", required_paths))
    issues.extend(validate_macos_info_plist(artifact_dir, app_contents / "Info.plist"))
    issues.extend(validate_checksum_manifest(artifact_dir, "macOS", required_paths))
    return issues


def validate_windows_artifact(artifact_dir: Path) -> list[str]:
    issues = validate_artifact_common(artifact_dir, label="Windows")
    if issues and not artifact_dir.is_dir():
        return issues

    issues.extend(validate_required_paths(artifact_dir, "Windows", WINDOWS_REQUIRED_PATHS))
    issues.extend(validate_checksum_manifest(artifact_dir, "Windows", WINDOWS_REQUIRED_PATHS))
    return issues


def validate_windows_installer_artifact(artifact_dir: Path) -> list[str]:
    issues = validate_artifact_common(artifact_dir, label="Windows installer")
    if issues and not artifact_dir.is_dir():
        return issues

    installer_paths = tuple(sorted(artifact_dir.glob(WINDOWS_INSTALLER_GLOB)))
    if not installer_paths:
        return [
            *issues,
            f"Windows installer artifact missing {WINDOWS_INSTALLER_GLOB}",
        ]

    required_paths = tuple(path.relative_to(artifact_dir) for path in installer_paths)
    issues.extend(
        validate_checksum_manifest(artifact_dir, "Windows installer", required_paths)
    )
    return issues


def validate_artifact_common(artifact_dir: Path, *, label: str) -> list[str]:
    if not artifact_dir.is_dir():
        return [f"missing {label} artifact directory: {artifact_dir.name}"]

    issues: list[str] = []
    if not (artifact_dir / "SHA256SUMS.txt").is_file():
        issues.append(f"{label} artifact missing SHA256SUMS.txt")
    relative_paths = [
        path.relative_to(artifact_dir)
        for path in artifact_dir.rglob("*")
        if path.is_file() or path.is_dir()
    ]
    if any(relative_path.name == "builder-debug.yml" for relative_path in relative_paths):
        issues.append(f"{label} artifact must not include builder-debug.yml")
    if any(part.startswith(".icon-") for relative_path in relative_paths for part in relative_path.parts):
        issues.append(f"{label} artifact must not include .icon-* scratch directories")
    for prefix in FORBIDDEN_PREFIXES:
        if any(_matches_prefix(relative_path, prefix) for relative_path in relative_paths):
            issues.append(f"{label} artifact must not include {prefix}")
    return issues


def validate_required_paths(
    artifact_dir: Path,
    label: str,
    required_paths: tuple[Path, ...],
) -> list[str]:
    return [
        f"{label} artifact missing {required_path.as_posix()}"
        for required_path in required_paths
        if not (artifact_dir / required_path).is_file()
    ]


def validate_checksum_manifest(
    artifact_dir: Path,
    label: str,
    required_paths: tuple[Path, ...],
) -> list[str]:
    manifest_path = artifact_dir / "SHA256SUMS.txt"
    if not manifest_path.is_file():
        return []

    entries = parse_checksum_manifest(manifest_path)
    issues: list[str] = []
    for required_path in required_paths:
        required_text = required_path.as_posix()
        if required_text not in entries:
            issues.append(f"{label} checksum manifest missing {required_text}")
    for relative_path, expected_digest in entries.items():
        target = artifact_dir / relative_path
        if not target.is_file():
            issues.append(f"{label} checksum manifest lists missing file {relative_path}")
            continue
        actual_digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            issues.append(f"{label} checksum mismatch for {relative_path}")
    return issues


def validate_macos_info_plist(artifact_dir: Path, info_plist_path: Path) -> list[str]:
    path = artifact_dir / info_plist_path
    if not path.is_file():
        return []

    try:
        payload = plistlib.loads(path.read_bytes())
    except (plistlib.InvalidFileException, ValueError) as exc:
        return [f"macOS artifact Info.plist is not valid plist: {exc}"]

    if not isinstance(payload, dict):
        return ["macOS artifact Info.plist is not a dictionary"]

    if any(payload.get(key) != MAC_BLUETOOTH_USAGE_DESCRIPTION for key in MAC_BLUETOOTH_USAGE_KEYS):
        return ["macOS artifact Info.plist missing Bluetooth usage descriptions"]
    return []


def parse_checksum_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        digest, separator, relative_path = line.partition("  ")
        if separator != "  " or not digest:
            entries[line] = ""
            continue
        entries[relative_path] = digest
    return entries


def find_macos_app_contents(artifact_dir: Path) -> Path | None:
    for info_plist in sorted(artifact_dir.glob("mac*/MiniX Print Studio.app/Contents/Info.plist")):
        return info_plist.parent.relative_to(artifact_dir)
    return None


def _matches_prefix(relative_path: Path, prefix: str) -> bool:
    path_text = relative_path.as_posix()
    return path_text == prefix.rstrip("/") or path_text.startswith(prefix)


if __name__ == "__main__":
    raise SystemExit(main())
