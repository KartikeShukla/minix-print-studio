from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_HISTORY_RANGE = "origin/main..HEAD"
GIT_LOG_FORMAT = "%H%x00%an%x00%ae%x00%cn%x00%ce"
PRIVATE_METADATA_MARKERS = (
    ".local",
    "localhost",
    "MacBook",
    "/Users/",
    "/home/",
    "C:\\Users\\",
)


@dataclass(frozen=True)
class HistoryRecord:
    commit: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate git author and committer metadata before public release."
    )
    parser.add_argument(
        "revision_range",
        nargs="?",
        default=DEFAULT_HISTORY_RANGE,
        help=f"Git revision range to inspect. Defaults to {DEFAULT_HISTORY_RANGE}.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    try:
        records = collect_history_records(root=root, revision_range=args.revision_range)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or "failed to read git history", file=sys.stderr)
        return 1

    issues = validate_history_records(records)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("public history check passed")
    return 0


def collect_history_records(*, root: Path, revision_range: str) -> list[HistoryRecord]:
    result = subprocess.run(
        ["git", "log", f"--format={GIT_LOG_FORMAT}", revision_range],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return parse_history_records(result.stdout)


def parse_history_records(text: str) -> list[HistoryRecord]:
    records: list[HistoryRecord] = []
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("\x00")
        if len(parts) != 5:
            raise ValueError("git log record must contain five NUL-delimited fields")
        records.append(
            HistoryRecord(
                commit=parts[0],
                author_name=parts[1],
                author_email=parts[2],
                committer_name=parts[3],
                committer_email=parts[4],
            )
        )
    return records


def validate_history_records(records: list[HistoryRecord]) -> list[str]:
    issues: list[str] = []
    for record in records:
        fields = (
            ("author name", record.author_name),
            ("author email", record.author_email),
            ("committer name", record.committer_name),
            ("committer email", record.committer_email),
        )
        for label, value in fields:
            for marker in PRIVATE_METADATA_MARKERS:
                if marker in value:
                    issues.append(
                        f"commit {record.commit[:12]} {label} contains private marker: "
                        f"{marker}"
                    )
                    break
    return issues


if __name__ == "__main__":
    raise SystemExit(main())
