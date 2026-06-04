from __future__ import annotations

Density = str
PaperMode = str

_DENSITY_BYTES: dict[Density, int] = {
    "light": 0x00,
    "medium": 0x01,
    "dark": 0x02,
}

_PAPER_MODE_BYTES: dict[PaperMode, int] = {
    "gap_label": 0x00,
    "black_mark": 0x01,
    "continuous": 0x02,
}


def build_set_density_command(density: Density) -> bytes:
    try:
        density_byte = _DENSITY_BYTES[density]
    except KeyError as exc:
        raise ValueError(f"unsupported density: {density}") from exc

    return bytes([0x10, 0xFF, 0x10, 0x00, density_byte])


def build_set_paper_mode_command(paper_mode: PaperMode) -> bytes:
    try:
        paper_byte = _PAPER_MODE_BYTES[paper_mode]
    except KeyError as exc:
        raise ValueError(f"unsupported paper mode: {paper_mode}") from exc

    return bytes([0x10, 0xFF, 0x84, paper_byte])


def build_wake_command() -> bytes:
    return b"\x00" * 12


def build_enable_mode_command() -> bytes:
    return bytes.fromhex("10 ff fe 01")


def build_feed_form_command() -> bytes:
    return bytes.fromhex("1d 0c")


def build_stop_mode_command() -> bytes:
    return bytes.fromhex("10 ff fe 45")


def build_raster_command(*, width_dots: int, height_dots: int, packed_raster: bytes) -> bytes:
    if width_dots <= 0 or width_dots % 8 != 0:
        raise ValueError("width_dots must be positive and divisible by 8")
    if height_dots <= 0:
        raise ValueError("height_dots must be positive")

    row_bytes = width_dots // 8
    expected_bytes = row_bytes * height_dots
    if len(packed_raster) != expected_bytes:
        raise ValueError(
            f"expected {expected_bytes} raster bytes for {width_dots}x{height_dots}, "
            f"got {len(packed_raster)}"
        )
    if row_bytes > 0xFFFF or height_dots > 0xFFFF:
        raise ValueError("raster dimensions exceed GS v 0 header limits")

    header = bytes(
        [
            0x1D,
            0x76,
            0x30,
            0x00,
            row_bytes & 0xFF,
            (row_bytes >> 8) & 0xFF,
            height_dots & 0xFF,
            (height_dots >> 8) & 0xFF,
        ]
    )
    return header + packed_raster
