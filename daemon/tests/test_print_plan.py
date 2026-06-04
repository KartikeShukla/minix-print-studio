import json
from pathlib import Path

from minixd.printing.planner import create_print_plan, reconstruct_raster_from_bands

PROFILE_PATH = Path("profiles/seznik-minix-s1-lyin48d-gy/profile.json")


def load_profile() -> dict[str, object]:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def test_print_plan_appends_tail_rows_and_segments_long_raster_without_loss() -> None:
    profile = load_profile()
    row_bytes = 48
    content_height = 10_000
    content_raster = bytes(index % 251 for index in range(row_bytes * content_height))

    package = create_print_plan(
        job_id="job_long",
        preview_id="prev_long",
        document_hash="sha256:document",
        content_raster=content_raster,
        content_height_dots=content_height,
        profile=profile,
        paper_mode="continuous",
        density="medium",
    )

    assert package.plan.content_height_dots == 10_000
    assert package.plan.tail_blank_rows_dots == 160
    assert package.plan.transfer_height_dots == 10_160
    assert package.plan.total_raster_bytes == 487_680
    assert package.plan.requires_long_print_mode is True
    assert len(package.bands) == 40
    assert package.bands[0].start_row == 0
    assert package.bands[0].height_dots == 256
    assert package.bands[-1].start_row == 9_984
    assert package.bands[-1].height_dots == 176
    assert package.transfer_raster.endswith(b"\x00" * (row_bytes * 160))
    assert reconstruct_raster_from_bands(package.bands) == package.transfer_raster
    assert package.plan.raster_hash == package.transfer_raster_hash


def test_print_plan_band_metadata_matches_payloads() -> None:
    profile = load_profile()
    row_bytes = 48
    content_height = 300
    content_raster = bytes([0xAA]) * row_bytes * content_height

    package = create_print_plan(
        job_id="job_short",
        preview_id="prev_short",
        document_hash="sha256:document",
        content_raster=content_raster,
        content_height_dots=content_height,
        profile=profile,
        paper_mode="continuous",
        density="medium",
    )

    for band in package.bands:
        assert band.raster_byte_length == row_bytes * band.height_dots
        assert len(band.raster) == band.raster_byte_length
        assert band.payload_bytes == 8 + band.raster_byte_length
        assert band.raster_byte_offset == row_bytes * band.start_row
        assert band.sha256.startswith("sha256:")
