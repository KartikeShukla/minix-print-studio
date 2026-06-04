from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from minixd.printing.planner import PrintPlanPackage, RasterBand, create_print_plan
from minixd.render.preview_store import PreviewBindingError, PreviewStore


class PrintRejectedError(ValueError):
    """Raised when a print request is blocked before physical output."""


@dataclass(frozen=True)
class PrintJob:
    job_id: str
    preview_id: str
    plan_id: str
    state: str
    phase: str
    completion_level: str
    completion_confidence: str
    requires_user_check: bool
    source: str
    copies: int
    bands_sent: int
    total_bands: int
    rows_sent: int
    total_rows: int
    bytes_sent: int
    total_bytes: int
    tail_blank_rows_dots: int
    safe_actions: list[str]


class PrintQueue:
    def __init__(
        self,
        *,
        profiles: list[dict[str, object]],
        preview_store: PreviewStore,
        mock: bool,
        job_store_path: Path | None = None,
    ) -> None:
        self._profiles = profiles
        self._preview_store = preview_store
        self._mock = mock
        self._jobs: dict[str, PrintJob] = {}
        self._segments: dict[str, list[RasterBand]] = {}
        self._job_store_path = job_store_path
        self._load_jobs()

    def print_preview(
        self,
        *,
        preview_id: str,
        approval_token: str,
        document_hash: str,
        render_settings_hash: str,
        profile_id: str,
        paper_mode: str,
        density: str,
        copies: int,
        source: str,
    ) -> PrintJob:
        if copies != 1:
            raise PrintRejectedError("mock queue currently supports exactly one copy")
        profile = self._find_profile(profile_id)
        try:
            preview = self._preview_store.verify(
                preview_id=preview_id,
                approval_token=approval_token,
                document_hash=document_hash,
                render_settings_hash=render_settings_hash,
            )
        except PreviewBindingError as exc:
            raise PrintRejectedError(str(exc)) from exc

        job_id = f"job_{uuid4().hex}"
        plan_package = create_print_plan(
            job_id=job_id,
            preview_id=preview.preview_id,
            document_hash=preview.document_hash,
            content_raster=preview.raster,
            content_height_dots=preview.height_dots,
            profile=profile,
            paper_mode=paper_mode,
            density=density,
        )
        job = self._mock_complete_unverified_job(
            job_id=job_id,
            preview_id=preview.preview_id,
            plan_package=plan_package,
            source=source,
            copies=copies,
        )
        self._jobs[job.job_id] = job
        self._segments[job.job_id] = plan_package.bands
        self._persist_jobs()
        return job

    def list_jobs(self) -> list[PrintJob]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> PrintJob | None:
        return self._jobs.get(job_id)

    def get_segments(self, job_id: str) -> list[RasterBand]:
        return self._segments.get(job_id, [])

    def _find_profile(self, profile_id: str) -> dict[str, object]:
        for profile in self._profiles:
            if profile.get("id") == profile_id:
                return profile
        raise PrintRejectedError(f"unknown profile: {profile_id}")

    def _mock_complete_unverified_job(
        self,
        *,
        job_id: str,
        preview_id: str,
        plan_package: PrintPlanPackage,
        source: str,
        copies: int,
    ) -> PrintJob:
        if not self._mock:
            raise PrintRejectedError("real printer transport is not implemented yet")
        return PrintJob(
            job_id=job_id,
            preview_id=preview_id,
            plan_id=plan_package.plan.plan_id,
            state="completed_unverified",
            phase="waiting_for_final_status",
            completion_level="unverified",
            completion_confidence="mock_data_sent_final_ack_missing",
            requires_user_check=True,
            source=source,
            copies=copies,
            bands_sent=len(plan_package.bands),
            total_bands=len(plan_package.bands),
            rows_sent=plan_package.plan.transfer_height_dots,
            total_rows=plan_package.plan.transfer_height_dots,
            bytes_sent=plan_package.plan.total_raster_bytes,
            total_bytes=plan_package.plan.total_raster_bytes,
            tail_blank_rows_dots=plan_package.plan.tail_blank_rows_dots,
            safe_actions=["confirm_complete", "feed_paper", "reprint_from_start"],
        )

    def _load_jobs(self) -> None:
        if self._job_store_path is None or not self._job_store_path.exists():
            return
        payload = json.loads(self._job_store_path.read_text(encoding="utf-8"))
        records = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            return
        for record in records:
            if not isinstance(record, dict):
                continue
            job_payload = record.get("job")
            segment_payloads = record.get("segments")
            if not isinstance(job_payload, dict) or not isinstance(segment_payloads, list):
                continue
            job = _deserialize_job(job_payload)
            self._jobs[job.job_id] = job
            self._segments[job.job_id] = [
                _deserialize_segment(segment)
                for segment in segment_payloads
                if isinstance(segment, dict)
            ]

    def _persist_jobs(self) -> None:
        if self._job_store_path is None:
            return
        self._job_store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "jobs": [
                {
                    "job": asdict(job),
                    "segments": [
                        _serialize_segment(segment)
                        for segment in self._segments.get(job.job_id, [])
                    ],
                }
                for job in self.list_jobs()
            ],
        }
        self._job_store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _deserialize_job(payload: dict[str, Any]) -> PrintJob:
    return PrintJob(
        job_id=_string(payload, "job_id"),
        preview_id=_string(payload, "preview_id"),
        plan_id=_string(payload, "plan_id"),
        state=_string(payload, "state"),
        phase=_string(payload, "phase"),
        completion_level=_string(payload, "completion_level"),
        completion_confidence=_string(payload, "completion_confidence"),
        requires_user_check=_bool(payload, "requires_user_check"),
        source=_string(payload, "source"),
        copies=_int(payload, "copies"),
        bands_sent=_int(payload, "bands_sent"),
        total_bands=_int(payload, "total_bands"),
        rows_sent=_int(payload, "rows_sent"),
        total_rows=_int(payload, "total_rows"),
        bytes_sent=_int(payload, "bytes_sent"),
        total_bytes=_int(payload, "total_bytes"),
        tail_blank_rows_dots=_int(payload, "tail_blank_rows_dots"),
        safe_actions=_string_list(payload, "safe_actions"),
    )


def _serialize_segment(segment: RasterBand) -> dict[str, object]:
    return {
        "index": segment.index,
        "start_row": segment.start_row,
        "height_dots": segment.height_dots,
        "raster_byte_offset": segment.raster_byte_offset,
        "raster_byte_length": segment.raster_byte_length,
        "payload_bytes": segment.payload_bytes,
        "sha256": segment.sha256,
    }


def _deserialize_segment(payload: dict[str, Any]) -> RasterBand:
    return RasterBand(
        index=_int(payload, "index"),
        start_row=_int(payload, "start_row"),
        height_dots=_int(payload, "height_dots"),
        raster_byte_offset=_int(payload, "raster_byte_offset"),
        raster_byte_length=_int(payload, "raster_byte_length"),
        payload_bytes=_int(payload, "payload_bytes"),
        sha256=_string(payload, "sha256"),
        raster=b"",
    )


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _bool(payload: dict[str, Any], key: str) -> bool:
    value = payload[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _int(payload: dict[str, Any], key: str) -> int:
    value = payload[key]
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a string list")
    return value
