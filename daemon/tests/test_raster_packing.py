import pytest

from minixd.raster.packing import calculate_black_coverage, pack_rows_msb, unpack_rows_msb


def test_pack_rows_uses_msb_first_black_bit_order() -> None:
    packed = pack_rows_msb(
        [
            [1, 0, 1, 0, 0, 0, 0, 1],
            [0, 1, 0, 1, 1, 1, 1, 0],
        ],
        width_dots=8,
    )

    assert packed == bytes([0b10100001, 0b01011110])


def test_pack_rows_rejects_non_byte_aligned_widths() -> None:
    with pytest.raises(ValueError, match="width_dots must be divisible by 8"):
        pack_rows_msb([[1, 0, 1]], width_dots=3)


def test_unpack_rows_round_trips_packed_raster() -> None:
    rows = [
        [1, 0, 0, 0, 0, 0, 0, 1],
        [0, 0, 0, 1, 1, 0, 0, 0],
    ]

    packed = pack_rows_msb(rows, width_dots=8)

    assert unpack_rows_msb(packed, width_dots=8, height_dots=2) == rows


def test_calculate_black_coverage_counts_set_bits() -> None:
    packed = bytes([0b11110000, 0b00000000])

    assert calculate_black_coverage(packed, width_dots=8, height_dots=2) == 0.25
