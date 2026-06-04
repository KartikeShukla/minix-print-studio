from __future__ import annotations

from dataclasses import dataclass
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
    ) -> None:
        self._profiles = profiles
        self._preview_store = preview_store
        self._mock = mock
        self._jobs: dict[str, PrintJob] = {}
        self._segments: dict[str, list[RasterBand]] = {}

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
