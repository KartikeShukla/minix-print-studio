from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from minixd.projects.store import ProjectRecord, ProjectStore


class CreateProjectRequest(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    document: dict[str, Any]


def create_projects_router(*, project_store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["projects"])

    @router.get("")
    def list_projects() -> dict[str, list[dict[str, object]]]:
        return {"projects": [_serialize_project_summary(record) for record in project_store.list()]}

    @router.post("", status_code=201)
    def create_project(request: CreateProjectRequest) -> dict[str, object]:
        record = project_store.create(name=request.name, document=request.document)
        return _serialize_project(record)

    @router.get("/{project_id}")
    def get_project(project_id: str) -> dict[str, object]:
        record = project_store.get(project_id)
        if record is None:
            raise HTTPException(status_code=404, detail="project not found")
        return _serialize_project(record)

    @router.put("/{project_id}")
    def update_project(project_id: str, request: CreateProjectRequest) -> dict[str, object]:
        record = project_store.update(
            project_id,
            name=request.name,
            document=request.document,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="project not found")
        return _serialize_project(record)

    @router.delete("/{project_id}", status_code=204)
    def delete_project(project_id: str) -> Response:
        deleted = project_store.delete(project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="project not found")
        return Response(status_code=204)

    return router


def _serialize_project(record: ProjectRecord) -> dict[str, object]:
    return {
        "projectId": record.project_id,
        "name": record.name,
        "document": record.document,
        "createdAt": _format_timestamp(record.created_at),
        "updatedAt": _format_timestamp(record.updated_at),
    }


def _serialize_project_summary(record: ProjectRecord) -> dict[str, object]:
    document_id = record.document.get("id")
    return {
        "projectId": record.project_id,
        "name": record.name,
        "documentId": document_id if isinstance(document_id, str) else "",
        "updatedAt": _format_timestamp(record.updated_at),
    }


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
