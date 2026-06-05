from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from minixd.projects.store import ProjectAssetRecord, ProjectRecord, ProjectStore


class CreateProjectRequest(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    document: dict[str, Any]


class UploadProjectAssetRequest(BaseModel):
    file_name: Annotated[str, Field(alias="fileName", min_length=1)]
    mime_type: Annotated[str, Field(alias="mimeType", min_length=1)]
    data_base64: Annotated[str, Field(alias="dataBase64", min_length=1)]


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

    @router.post("/{project_id}/assets", status_code=201)
    def upload_asset(project_id: str, request: UploadProjectAssetRequest) -> dict[str, object]:
        _validate_image_mime_type(request.mime_type)
        record = project_store.add_asset(
            project_id,
            file_name=request.file_name,
            mime_type=request.mime_type,
            data=_decode_base64(request.data_base64),
        )
        if record is None:
            raise HTTPException(status_code=404, detail="project not found")
        return _serialize_asset(record)

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


def _serialize_asset(record: ProjectAssetRecord) -> dict[str, object]:
    return {
        "assetId": record.asset_id,
        "sha256": record.sha256,
        "fileName": record.file_name,
        "mimeType": record.mime_type,
        "byteLength": record.byte_length,
    }


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _decode_base64(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="asset dataBase64 is invalid") from exc


def _validate_image_mime_type(mime_type: str) -> None:
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=422, detail="asset mimeType is not supported")
