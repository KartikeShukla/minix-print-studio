from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


DEFAULT_MANIFEST_NAME = "SHA256SUMS.txt"
SKIPPED_RELEASE_FILES = {"builder-debug.yml"}
SKIPPED_RELEASE_DIR_PREFIXES = (".icon-",)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a deterministic SHA-256 manifest for release artifacts."
    )
    parser.add_argument("release_dir", type=Path, help="Directory containing release artifacts.")
    parser.add_argument(
        "--output-name",
        default=DEFAULT_MANIFEST_NAME,
        help=f"Manifest filename inside release_dir. Defaults to {DEFAULT_MANIFEST_NAME}.",
    )
    args = parser.parse_args()

    release_dir = args.release_dir.resolve()
    try:
        manifest = write_release_checksums(release_dir, output_name=args.output_name)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"wrote {manifest.relative_to(release_dir)}")
    return 0


def write_release_checksums(
    release_dir: Path, *, output_name: str = DEFAULT_MANIFEST_NAME
) -> Path:
    release_dir = release_dir.resolve()
    if not release_dir.is_dir():
        raise ValueError(f"release directory does not exist: {release_dir}")
    if Path(output_name).name != output_name:
        raise ValueError("output name must be a filename, not a path")

    manifest_path = release_dir / output_name
    entries = [_checksum_entry(path, release_dir) for path in _release_files(release_dir, manifest_path)]
    manifest_text = "\n".join(f"{digest}  {relative_path}" for digest, relative_path in entries)
    if manifest_text:
        manifest_text += "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    return manifest_path


def _release_files(release_dir: Path, manifest_path: Path) -> list[Path]:
    files = [
        path
        for path in release_dir.rglob("*")
        if path.is_file()
        and path.resolve() != manifest_path.resolve()
        and not _is_electron_builder_scratch_path(path.relative_to(release_dir))
    ]
    return sorted(files, key=lambda path: path.relative_to(release_dir).as_posix())


def _is_electron_builder_scratch_path(relative_path: Path) -> bool:
    if relative_path.as_posix() in SKIPPED_RELEASE_FILES:
        return True
    return any(part.startswith(SKIPPED_RELEASE_DIR_PREFIXES) for part in relative_path.parts)


def _checksum_entry(path: Path, release_dir: Path) -> tuple[str, str]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    relative_path = path.relative_to(release_dir).as_posix()
    return digest, relative_path


if __name__ == "__main__":
    raise SystemExit(main())
