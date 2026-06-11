from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_release_evidence import validate_packaged_app_smoke  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-check packaged MiniX Print Studio app bundles."
    )
    parser.add_argument(
        "release_dir",
        type=Path,
        help="Path to dist/release after an electron-builder package command.",
    )
    args = parser.parse_args(argv)

    issues = validate_packaged_release_dir(args.release_dir)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("packaged app smoke check passed")
    return 0


def validate_packaged_release_dir(release_dir: Path) -> list[str]:
    release_dir = release_dir.resolve()
    if not release_dir.is_dir():
        return [f"release directory does not exist: {release_dir}"]

    app_asars = find_packaged_app_asars(release_dir)
    if not app_asars:
        return ["packaged app smoke found no unpacked MiniX app bundles"]

    issues: list[str] = []
    for label, asar_path in app_asars:
        issues.extend(validate_packaged_app_smoke(asar_path, label=label))
    return issues


def find_packaged_app_asars(release_dir: Path) -> list[tuple[str, Path]]:
    app_asars: list[tuple[str, Path]] = []
    direct_mac_asar = release_dir / "MiniX Print Studio.app/Contents/Resources/app.asar"
    if direct_mac_asar.is_file():
        app_asars.append(("macOS", direct_mac_asar))
    direct_windows_asar = release_dir / "resources/app.asar"
    if direct_windows_asar.is_file():
        app_asars.append(("Windows", direct_windows_asar))
    for asar_path in sorted(
        release_dir.glob("mac*/MiniX Print Studio.app/Contents/Resources/app.asar")
    ):
        app_asars.append(("macOS", asar_path))
    for asar_path in sorted(release_dir.glob("win*-unpacked/resources/app.asar")):
        app_asars.append(("Windows", asar_path))
    return app_asars


if __name__ == "__main__":
    raise SystemExit(main())
