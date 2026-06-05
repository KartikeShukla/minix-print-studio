from __future__ import annotations

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str
    document: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectStore:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root
        self._records: dict[str, ProjectRecord] = {}
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)
            self._load_existing()

    def create(self, *, name: str, document: dict[str, Any]) -> ProjectRecord:
        now = _now()
        record = ProjectRecord(
            project_id=f"prj_{uuid.uuid4().hex[:12]}",
            name=name,
            document=deepcopy(document),
            created_at=now,
            updated_at=now,
        )
        self._records[record.project_id] = record
        self._persist(record)
        return record

    def list(self) -> list[ProjectRecord]:
        return sorted(
            self._records.values(),
            key=lambda record: (record.updated_at, record.project_id),
            reverse=True,
        )

    def get(self, project_id: str) -> ProjectRecord | None:
        return self._records.get(project_id)

    def _load_existing(self) -> None:
        if self._root is None:
            return
        for project_path in sorted(self._root.glob("*/project.json")):
            record = _decode_record(project_path.read_text(encoding="utf-8"))
            self._records[record.project_id] = record

    def _persist(self, record: ProjectRecord) -> None:
        if self._root is None:
            return
        project_dir = self._root / record.project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(_encode_record(record), indent=2, sort_keys=True)
        (project_dir / "project.json").write_text(f"{payload}\n", encoding="utf-8")


def _encode_record(record: ProjectRecord) -> dict[str, Any]:
    return {
        "projectId": record.project_id,
        "name": record.name,
        "document": deepcopy(record.document),
        "createdAt": _format_timestamp(record.created_at),
        "updatedAt": _format_timestamp(record.updated_at),
    }


def _decode_record(text: str) -> ProjectRecord:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("project.json must contain an object")
    project_id = _string(payload, "projectId")
    name = _string(payload, "name")
    document = payload.get("document")
    if not isinstance(document, dict):
        raise ValueError("project document must be an object")
    return ProjectRecord(
        project_id=project_id,
        name=name,
        document=deepcopy(document),
        created_at=_parse_timestamp(_string(payload, "createdAt")),
        updated_at=_parse_timestamp(_string(payload, "updatedAt")),
    )


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
