from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT_REQUIRED_PACKAGE_SCRIPTS = {
    "release-package-check": "node scripts/run_python.mjs scripts/validate_release_packaging.py",
    "build:sidecars": "node scripts/run_python.mjs scripts/build_sidecars.py",
    "package:mac": "pnpm --filter @minix/desktop package:mac",
    "package:win": "pnpm --filter @minix/desktop package:win",
}

DESKTOP_REQUIRED_PACKAGE_SCRIPTS = {
    "package:mac": "pnpm build && pnpm --workspace-root build:sidecars --target-platform darwin && cross-env ELECTRON_CACHE=../../dist/electron-cache ELECTRON_BUILDER_CACHE=../../dist/electron-builder-cache electron-builder --config electron-builder.yml --mac --dir --publish never",
    "package:win": "pnpm build && pnpm --workspace-root build:sidecars --target-platform win32 && cross-env ELECTRON_CACHE=../../dist/electron-cache ELECTRON_BUILDER_CACHE=../../dist/electron-builder-cache electron-builder --config electron-builder.yml --win --dir --x64 --publish never",
}

BUILDER_CONFIG_PATH = Path("apps/desktop/electron-builder.yml")
RELEASE_PACKAGE_WORKFLOW_PATH = Path(".github/workflows/release-package.yml")
REQUIRED_PACKAGE_ICON_PATHS = (
    Path("apps/desktop/build/icon-source.svg"),
    Path("apps/desktop/build/icon.png"),
    Path("apps/desktop/build/icon.ico"),
)
BUILDER_REQUIRED_SNIPPETS = (
    "appId: org.minix.printstudio",
    "productName: MiniX Print Studio",
    "output: ../../dist/release",
    "from: ../../dist/sidecars",
    "to: sidecars",
    "main: out/main/index.js",
    "icon: build/icon.png",
    "icon: build/icon.ico",
    "signAndEditExecutable: false",
    "publish: null",
)
FORBIDDEN_PACKAGED_PREFIXES = (
    "runtime/",
    "logs/",
    "diagnostics/",
    "previews/",
    "jobs/",
    "hardware-artifacts/",
)
PRIVATE_PATH_MARKERS = (
    "/Users/",
    "/home/",
    "C:\\Users\\",
)
RELEASE_WORKFLOW_REQUIRED_ARTIFACT_EXCLUSIONS = (
    "!dist/release/builder-debug.yml",
    "!dist/release/.icon-*",
)

RELEASE_WORKFLOW_REQUIRED_ARTIFACT_NAMES = {
    "minix-print-studio-macos-unsigned": (
        "release package workflow missing macOS unsigned artifact name"
    ),
    "minix-print-studio-windows-unsigned": (
        "release package workflow missing Windows unsigned artifact name"
    ),
}

RELEASE_WORKFLOW_REQUIRED_SNIPPETS = (
    ("pnpm/action-setup@v4", "release package workflow missing pnpm setup"),
    ("actions/setup-node@v4", "release package workflow missing Node setup"),
    ("actions/setup-python@v5", "release package workflow missing Python setup"),
    (
        "pnpm install --frozen-lockfile",
        "release package workflow missing command: pnpm install --frozen-lockfile",
    ),
    (
        "python -m pip install -e daemon[dev] -e mcp[dev]",
        "release package workflow missing command: "
        "python -m pip install -e daemon[dev] -e mcp[dev]",
    ),
    (
        "pnpm release-package-check",
        "release package workflow missing command: pnpm release-package-check",
    ),
    ("pnpm package:mac", "release package workflow missing command: pnpm package:mac"),
    ("pnpm package:win", "release package workflow missing command: pnpm package:win"),
    (
        "node scripts/run_python.mjs scripts/write_release_checksums.py dist/release",
        "release package workflow missing command: "
        "node scripts/run_python.mjs scripts/write_release_checksums.py dist/release",
    ),
)


def main() -> int:
    root = Path.cwd()
    issues = validate_repository(root)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("release packaging check passed")
    return 0


def validate_repository(root: Path) -> list[str]:
    issues: list[str] = []
    root_package = _read_package_scripts(root / "package.json", "package.json")
    desktop_package = _read_package_scripts(
        root / "apps" / "desktop" / "package.json",
        "apps/desktop/package.json",
    )
    issues.extend(
        validate_package_scripts(
            root_scripts=root_package.scripts,
            desktop_scripts=desktop_package.scripts,
        )
    )
    issues.extend(root_package.issues)
    issues.extend(desktop_package.issues)

    builder_config = root / BUILDER_CONFIG_PATH
    if not builder_config.is_file():
        issues.append(f"missing required file: {BUILDER_CONFIG_PATH.as_posix()}")
        return issues

    text = builder_config.read_text(encoding="utf-8")
    issues.extend(validate_builder_config_text(text))
    for snippet in BUILDER_REQUIRED_SNIPPETS:
        if snippet not in text:
            issues.append(f"electron-builder config missing required setting: {snippet}")
    for icon_path in REQUIRED_PACKAGE_ICON_PATHS:
        if not (root / icon_path).is_file():
            issues.append(f"missing required package icon asset: {icon_path.as_posix()}")

    release_workflow = root / RELEASE_PACKAGE_WORKFLOW_PATH
    if not release_workflow.is_file():
        issues.append(f"missing required file: {RELEASE_PACKAGE_WORKFLOW_PATH.as_posix()}")
    else:
        issues.extend(
            validate_release_package_workflow_text(
                release_workflow.read_text(encoding="utf-8")
            )
        )
    return issues


def validate_package_scripts(
    *,
    root_scripts: dict[str, object],
    desktop_scripts: dict[str, object],
) -> list[str]:
    issues: list[str] = []
    for script_name, command in ROOT_REQUIRED_PACKAGE_SCRIPTS.items():
        if root_scripts.get(script_name) != command:
            issues.append(f"package.json missing {script_name} script")
    for script_name, command in DESKTOP_REQUIRED_PACKAGE_SCRIPTS.items():
        if desktop_scripts.get(script_name) != command:
            issues.append(f"apps/desktop/package.json missing {script_name} script")
    return issues


def validate_builder_config_text(text: str) -> list[str]:
    issues: list[str] = []
    for prefix in FORBIDDEN_PACKAGED_PREFIXES:
        if _includes_forbidden_packaged_prefix(text, prefix):
            issues.append(f"electron-builder config must exclude {prefix}")
    if _contains_signing_identity(text):
        issues.append("electron-builder config must not contain a signing identity")
    if _publishing_enabled(text):
        issues.append("electron-builder config must keep publishing disabled")
    if not _sidecar_resources_included(text):
        issues.append("electron-builder config must include sidecar binaries")
    if not _windows_resource_editing_disabled(text):
        issues.append("electron-builder config must disable Windows executable resource editing")
    if not _mac_icon_configured(text):
        issues.append("electron-builder config must set mac icon: build/icon.png")
    if not _windows_icon_configured(text):
        issues.append("electron-builder config must set Windows icon: build/icon.ico")
    for marker in PRIVATE_PATH_MARKERS:
        if marker in text:
            issues.append(f"electron-builder config contains private path marker: {marker}")
            break
    return issues


def validate_release_package_workflow_text(text: str) -> list[str]:
    issues: list[str] = []
    if "workflow_dispatch:" not in text:
        issues.append("release package workflow must support manual workflow_dispatch")
    if "runs-on: macos-latest" not in text and "os: macos-latest" not in text:
        issues.append("release package workflow missing macOS runner")
    if "runs-on: windows-latest" not in text and "os: windows-latest" not in text:
        issues.append("release package workflow missing Windows runner")
    issues.extend(
        issue
        for snippet, issue in RELEASE_WORKFLOW_REQUIRED_SNIPPETS
        if snippet not in text
    )
    if "actions/upload-artifact@v4" not in text:
        issues.append("release package workflow missing artifact upload step")
    issues.extend(
        issue
        for artifact_name, issue in RELEASE_WORKFLOW_REQUIRED_ARTIFACT_NAMES.items()
        if artifact_name not in text
    )
    if any(snippet not in text for snippet in RELEASE_WORKFLOW_REQUIRED_ARTIFACT_EXCLUSIONS):
        issues.append("release package workflow must exclude electron-builder scratch artifacts")
    return issues


class _PackageScripts:
    def __init__(self, *, scripts: dict[str, object], issues: list[str]) -> None:
        self.scripts = scripts
        self.issues = issues


def _read_package_scripts(path: Path, label: str) -> _PackageScripts:
    if not path.is_file():
        return _PackageScripts(scripts={}, issues=[f"missing required file: {label}"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    scripts = payload.get("scripts")
    if not isinstance(scripts, dict):
        return _PackageScripts(scripts={}, issues=[f"{label} missing scripts object"])
    return _PackageScripts(scripts=scripts, issues=[])


def _includes_forbidden_packaged_prefix(text: str, prefix: str) -> bool:
    include_pattern = re.compile(rf"(?m)^\s*-\s+['\"]?{re.escape(prefix)}")
    exclude_pattern = re.compile(rf"(?m)^\s*-\s+['\"]?!{re.escape(prefix)}")
    return bool(include_pattern.search(text)) and not bool(exclude_pattern.search(text))


def _contains_signing_identity(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("identity:") and stripped != "identity: null":
            return True
    return False


def _publishing_enabled(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("publish:") and stripped not in {"publish: null", "publish: never"}:
            return True
    return False


def _windows_resource_editing_disabled(text: str) -> bool:
    for line in text.splitlines():
        if line.strip() == "signAndEditExecutable: false":
            return True
    return False


def _mac_icon_configured(text: str) -> bool:
    return "icon: build/icon.png" in text


def _windows_icon_configured(text: str) -> bool:
    return "icon: build/icon.ico" in text


def _sidecar_resources_included(text: str) -> bool:
    return "from: ../../dist/sidecars" in text and "to: sidecars" in text


if __name__ == "__main__":
    raise SystemExit(main())
