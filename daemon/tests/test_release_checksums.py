from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKSUM_SCRIPT = PROJECT_ROOT / "scripts" / "write_release_checksums.py"


def test_release_checksum_script_writes_relative_sha256_manifest(tmp_path: Path) -> None:
    assert CHECKSUM_SCRIPT.is_file(), "missing release checksum script"
    checksum_script = _load_checksum_script()
    package_root = tmp_path / "release"
    app_info = package_root / "MiniX Print Studio.app" / "Contents" / "Info.plist"
    sidecar = package_root / "sidecars" / "minixd"
    app_info.parent.mkdir(parents=True)
    sidecar.parent.mkdir(parents=True)
    app_info.write_text("bundle", encoding="utf-8")
    sidecar.write_bytes(b"sidecar")

    manifest_path = checksum_script.write_release_checksums(package_root)

    assert manifest_path == package_root / "SHA256SUMS.txt"
    assert manifest_path.read_text(encoding="utf-8").splitlines() == [
        f"{_sha256(app_info)}  MiniX Print Studio.app/Contents/Info.plist",
        f"{_sha256(sidecar)}  sidecars/minixd",
    ]


def test_release_checksum_cli_accepts_relative_release_directory(tmp_path: Path) -> None:
    package_root = tmp_path / "release"
    package_root.mkdir()
    (package_root / "artifact.txt").write_text("release", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(CHECKSUM_SCRIPT), package_root.relative_to(tmp_path).as_posix()],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "wrote SHA256SUMS.txt"
    assert (package_root / "SHA256SUMS.txt").is_file()


def test_release_checksum_script_omits_electron_builder_scratch_files(
    tmp_path: Path,
) -> None:
    checksum_script = _load_checksum_script()
    package_root = tmp_path / "release"
    package_root.mkdir()
    (package_root / "builder-debug.yml").write_text("debug", encoding="utf-8")
    icon_cache = package_root / ".icon-icns"
    icon_cache.mkdir()
    (icon_cache / "icon.icns").write_bytes(b"cache")
    artifact = package_root / "mac-arm64" / "MiniX Print Studio.app" / "Contents" / "Info.plist"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("bundle", encoding="utf-8")

    manifest_path = checksum_script.write_release_checksums(package_root)

    assert manifest_path.read_text(encoding="utf-8").splitlines() == [
        f"{_sha256(artifact)}  mac-arm64/MiniX Print Studio.app/Contents/Info.plist",
    ]


def _load_checksum_script() -> object:
    spec = importlib.util.spec_from_file_location("write_release_checksums", CHECKSUM_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
