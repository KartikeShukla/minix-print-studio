import pytest

from minixd.protocol.aiyin import (
    build_enable_mode_command,
    build_feed_form_command,
    build_info_command,
    build_raster_command,
    build_set_density_command,
    build_set_paper_mode_command,
    build_stop_mode_command,
    build_wake_command,
)


def test_density_commands_use_known_aiyin_mapping() -> None:
    assert build_set_density_command("light") == bytes.fromhex("10 ff 10 00 00")
    assert build_set_density_command("medium") == bytes.fromhex("10 ff 10 00 01")
    assert build_set_density_command("dark") == bytes.fromhex("10 ff 10 00 02")


def test_paper_mode_commands_use_known_aiyin_mapping() -> None:
    assert build_set_paper_mode_command("gap_label") == bytes.fromhex("10 ff 84 00")
    assert build_set_paper_mode_command("black_mark") == bytes.fromhex("10 ff 84 01")
    assert build_set_paper_mode_command("continuous") == bytes.fromhex("10 ff 84 02")


def test_fixed_protocol_commands_match_spec_sequence() -> None:
    assert build_wake_command() == b"\x00" * 12
    assert build_enable_mode_command() == bytes.fromhex("10 ff fe 01")
    assert build_feed_form_command() == bytes.fromhex("1d 0c")
    assert build_stop_mode_command() == bytes.fromhex("10 ff fe 45")


def test_read_only_info_commands_match_aiyin_query_bytes() -> None:
    assert build_info_command("model") == bytes.fromhex("10 ff 20 f0")
    assert build_info_command("firmware") == bytes.fromhex("10 ff 20 f1")
    assert build_info_command("version") == bytes.fromhex("10 ff 20 f1")


def test_gs_v0_raster_command_encodes_row_bytes_and_height_little_endian() -> None:
    payload = bytes(range(96))

    command = build_raster_command(width_dots=384, height_dots=2, packed_raster=payload)

    assert command[:8] == bytes.fromhex("1d 76 30 00 30 00 02 00")
    assert command[8:] == payload


def test_raster_command_rejects_payload_with_wrong_byte_count() -> None:
    with pytest.raises(ValueError, match="expected 96 raster bytes"):
        build_raster_command(width_dots=384, height_dots=2, packed_raster=b"\x00")
