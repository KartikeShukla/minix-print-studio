from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT_REQUIRED_PACKAGE_SCRIPTS = {
    "release-package-check": "python3 scripts/validate_release_packaging.py",
    "package:mac": "pnpm --filter @minix/desktop package:mac",
    "package:win": "pnpm --filter @minix/desktop package:win",
}

DESKTOP_REQUIRED_PACKAGE_SCRIPTS = {
    "package:mac": "pnpm build && cross-env ELECTRON_CACHE=../../dist/electron-cache ELECTRON_BUILDER_CACHE=../../dist/electron-builder-cache electron-builder --config electron-builder.yml --mac --dir --publish never",
    "package:win": "pnpm build && cross-env ELECTRON_CACHE=../../dist/electron-cache ELECTRON_BUILDER_CACHE=../../dist/electron-builder-cache electron-builder --config electron-builder.yml --win --dir --publish never",
}

BUILDER_CONFIG_PATH = Path("apps/desktop/electron-builder.yml")
BUILDER_REQUIRED_SNIPPETS = (
    "appId: org.minix.printstudio",
    "productName: MiniX Print Studio",
    "output: ../../dist/release",
    "main: out/main/index.js",
    "publish: null",
)
FORBIDDEN_PACKAGED_PREFIXES = (
    "runtime/",
    "logs/",
    "diagnostics/",
    "previews/",
    "jobs/",
)
PRIVATE_PATH_MARKERS = (
    "/Users/",
    "/home/",
    "C:\\Users\\",
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
    for marker in PRIVATE_PATH_MARKERS:
        if marker in text:
            issues.append(f"electron-builder config contains private path marker: {marker}")
            break
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


if __name__ == "__main__":
    raise SystemExit(main())
