from __future__ import annotations

from collections.abc import Sequence

PixelRow = Sequence[int | bool]


def pack_rows_msb(rows: Sequence[PixelRow], *, width_dots: int) -> bytes:
    if width_dots <= 0 or width_dots % 8 != 0:
        raise ValueError("width_dots must be divisible by 8")

    packed = bytearray()
    for row_index, row in enumerate(rows):
        if len(row) != width_dots:
            raise ValueError(
                f"row {row_index} has {len(row)} pixels; expected {width_dots}"
            )

        for byte_start in range(0, width_dots, 8):
            value = 0
            for bit_index, pixel in enumerate(row[byte_start : byte_start + 8]):
                if pixel:
                    value |= 1 << (7 - bit_index)
            packed.append(value)

    return bytes(packed)


def unpack_rows_msb(packed_raster: bytes, *, width_dots: int, height_dots: int) -> list[list[int]]:
    if width_dots <= 0 or width_dots % 8 != 0:
        raise ValueError("width_dots must be divisible by 8")
    if height_dots < 0:
        raise ValueError("height_dots must be non-negative")

    row_bytes = width_dots // 8
    expected_bytes = row_bytes * height_dots
    if len(packed_raster) != expected_bytes:
        raise ValueError(f"expected {expected_bytes} raster bytes, got {len(packed_raster)}")

    rows: list[list[int]] = []
    for row_start in range(0, len(packed_raster), row_bytes):
        row: list[int] = []
        for value in packed_raster[row_start : row_start + row_bytes]:
            for bit_index in range(8):
                row.append(1 if value & (1 << (7 - bit_index)) else 0)
        rows.append(row)
    return rows


def calculate_black_coverage(packed_raster: bytes, *, width_dots: int, height_dots: int) -> float:
    if width_dots <= 0 or height_dots <= 0:
        raise ValueError("width_dots and height_dots must be positive")
    row_bytes = width_dots // 8
    expected_bytes = row_bytes * height_dots
    if width_dots % 8 != 0:
        raise ValueError("width_dots must be divisible by 8")
    if len(packed_raster) != expected_bytes:
        raise ValueError(f"expected {expected_bytes} raster bytes, got {len(packed_raster)}")

    black_pixels = sum(value.bit_count() for value in packed_raster)
    return black_pixels / (width_dots * height_dots)
