from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RasterBand:
    index: int
    start_row: int
    height_dots: int
    raster_byte_offset: int
    raster_byte_length: int
    payload_bytes: int
    black_dot_count: int
    black_coverage: float
    cooldown_after_ms: int
    sha256: str
    raster: bytes


@dataclass(frozen=True)
class PrintPlan:
    plan_id: str
    job_id: str
    preview_id: str
    document_hash: str
    raster_hash: str
    profile_id: str
    paper_mode: str
    density: str
    width_dots: int
    content_height_dots: int
    tail_blank_rows_dots: int
    transfer_height_dots: int
    row_bytes: int
    total_raster_bytes: int
    requires_long_print_mode: bool


@dataclass(frozen=True)
class PrintPlanPackage:
    plan: PrintPlan
    transfer_raster: bytes
    transfer_raster_hash: str
    bands: list[RasterBand]


def create_print_plan(
    *,
    job_id: str,
    preview_id: str,
    document_hash: str,
    content_raster: bytes,
    content_height_dots: int,
    profile: dict[str, Any],
    paper_mode: str,
    density: str,
) -> PrintPlanPackage:
    print_config = _dict_value(profile, "print")
    long_print_config = _dict_value(print_config, "longPrint")
    profile_id = _string_value(profile, "id")
    width_dots = _int_value(print_config, "widthDots")
    row_bytes = _int_value(print_config, "rowBytes")
    max_band_height = _int_value(long_print_config, "defaultMaxBandHeightDots")
    long_print_threshold = _int_value(long_print_config, "longPrintThresholdDots")
    thermal_pacing = _optional_dict_value(long_print_config, "thermalPacing")
    tail_rows = (
        _int_value(long_print_config, "appendTailBlankRowsContinuous")
        if paper_mode == "continuous"
        else 0
    )

    if width_dots % 8 != 0:
        raise ValueError("profile widthDots must be divisible by 8")
    if row_bytes != width_dots // 8:
        raise ValueError("profile rowBytes must equal widthDots / 8")
    if content_height_dots <= 0:
        raise ValueError("content_height_dots must be positive")
    expected_content_bytes = row_bytes * content_height_dots
    if len(content_raster) != expected_content_bytes:
        raise ValueError(
            f"expected {expected_content_bytes} content raster bytes, got {len(content_raster)}"
        )

    transfer_raster = content_raster + (b"\x00" * row_bytes * tail_rows)
    transfer_height = content_height_dots + tail_rows
    transfer_hash = _sha256(transfer_raster)
    bands = _segment_transfer_raster(
        transfer_raster,
        row_bytes=row_bytes,
        max_band_height=max_band_height,
        thermal_pacing=thermal_pacing,
    )

    plan = PrintPlan(
        plan_id=f"plan_{job_id}",
        job_id=job_id,
        preview_id=preview_id,
        document_hash=document_hash,
        raster_hash=transfer_hash,
        profile_id=profile_id,
        paper_mode=paper_mode,
        density=density,
        width_dots=width_dots,
        content_height_dots=content_height_dots,
        tail_blank_rows_dots=tail_rows,
        transfer_height_dots=transfer_height,
        row_bytes=row_bytes,
        total_raster_bytes=len(transfer_raster),
        requires_long_print_mode=content_height_dots >= long_print_threshold,
    )
    return PrintPlanPackage(
        plan=plan,
        transfer_raster=transfer_raster,
        transfer_raster_hash=transfer_hash,
        bands=bands,
    )


def reconstruct_raster_from_bands(bands: list[RasterBand]) -> bytes:
    expected_start = 0
    chunks: list[bytes] = []
    for band in bands:
        if band.start_row != expected_start:
            raise ValueError(
                f"band {band.index} starts at row {band.start_row}; expected {expected_start}"
            )
        chunks.append(band.raster)
        expected_start += band.height_dots
    return b"".join(chunks)


def _segment_transfer_raster(
    transfer_raster: bytes,
    *,
    row_bytes: int,
    max_band_height: int,
    thermal_pacing: dict[str, Any] | None,
) -> list[RasterBand]:
    if row_bytes <= 0:
        raise ValueError("row_bytes must be positive")
    if max_band_height <= 0:
        raise ValueError("max_band_height must be positive")
    if len(transfer_raster) % row_bytes != 0:
        raise ValueError("transfer raster length must contain whole rows")

    total_rows = len(transfer_raster) // row_bytes
    bands: list[RasterBand] = []
    start_row = 0
    index = 0
    while start_row < total_rows:
        height = min(max_band_height, total_rows - start_row)
        byte_offset = start_row * row_bytes
        byte_length = height * row_bytes
        raster = transfer_raster[byte_offset : byte_offset + byte_length]
        black_dot_count = sum(value.bit_count() for value in raster)
        total_dots = row_bytes * 8 * height
        black_coverage = black_dot_count / total_dots if total_dots else 0.0
        is_last_band = start_row + height >= total_rows
        bands.append(
            RasterBand(
                index=index,
                start_row=start_row,
                height_dots=height,
                raster_byte_offset=byte_offset,
                raster_byte_length=byte_length,
                payload_bytes=8 + byte_length,
                black_dot_count=black_dot_count,
                black_coverage=black_coverage,
                cooldown_after_ms=_cooldown_after_ms(
                    black_coverage=black_coverage,
                    is_last_band=is_last_band,
                    thermal_pacing=thermal_pacing,
                ),
                sha256=_sha256(raster),
                raster=raster,
            )
        )
        start_row += height
        index += 1

    return bands


def _cooldown_after_ms(
    *,
    black_coverage: float,
    is_last_band: bool,
    thermal_pacing: dict[str, Any] | None,
) -> int:
    if is_last_band or thermal_pacing is None or thermal_pacing.get("enabled") is False:
        return 0
    base_delay = _optional_int_value(thermal_pacing, "baseInterBandDelayMs") or 0
    coverage_threshold = _optional_float_value(thermal_pacing, "cooldownBandCoverage")
    ms_per_coverage_point = (
        _optional_int_value(thermal_pacing, "cooldownMsPerCoveragePoint") or 0
    )
    max_cooldown = _optional_int_value(thermal_pacing, "maxCooldownMs")
    cooldown = base_delay
    if coverage_threshold is not None and black_coverage > coverage_threshold:
        excess_ms = round((black_coverage - coverage_threshold) * ms_per_coverage_point, 6)
        cooldown += math.ceil(excess_ms)
    if max_cooldown is not None:
        cooldown = min(cooldown, max_cooldown)
    return max(0, cooldown)


def _sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _dict_value(source: dict[str, Any], key: str) -> dict[str, Any]:
    value = source[key]
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _optional_dict_value(source: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = source.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _string_value(source: dict[str, Any], key: str) -> str:
    value = source[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _int_value(source: dict[str, Any], key: str) -> int:
    value = source[key]
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _optional_int_value(source: dict[str, Any], key: str) -> int | None:
    value = source.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _optional_float_value(source: dict[str, Any], key: str) -> float | None:
    value = source.get(key)
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number")
    return float(value)
