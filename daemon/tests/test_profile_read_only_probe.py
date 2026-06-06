import asyncio
from dataclasses import dataclass

from minixd.ble.bleak_adapter import ReadOnlyBleSession
from minixd.ble.profile_probe import ProfileReadOnlyProbe

FF00 = "0000ff00-0000-1000-8000-00805f9b34fb"
FF01 = "0000ff01-0000-1000-8000-00805f9b34fb"
FF02 = "0000ff02-0000-1000-8000-00805f9b34fb"

PROFILE = {
    "id": "seznik-minix-s1-lyin48d-gy",
    "modelResponse": "S1_LYiN48D_GY",
    "observedFirmware": ["V1.9.11"],
    "ble": {
        "serviceUuid": FF00,
        "writeCharUuid": FF02,
        "writeWithResponse": True,
    },
    "readOnly": {
        "modelCommandHex": "aa 01",
        "firmwareCommandHex": "aa 02",
        "responseEncoding": "ascii-substring",
    },
}


@dataclass
class WriteCall:
    characteristic: str
    payload: bytes
    response: bool | None


class FakeReadOnlyClient:
    def __init__(self, raw_notifications: list[str]) -> None:
        self.raw_notifications = raw_notifications
        self.writes: list[WriteCall] = []

    async def write_gatt_char(
        self,
        characteristic: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None:
        self.writes.append(WriteCall(characteristic, data, response))
        if data == bytes.fromhex("aa 01"):
            self.raw_notifications.append(b"\x02S1_LYiN48D_GY\x00".hex())
        if data == bytes.fromhex("aa 02"):
            self.raw_notifications.append(b"V1.9.11".hex())


class DelayedStatusThenTextClient:
    def __init__(self, raw_notifications: list[str]) -> None:
        self.raw_notifications = raw_notifications

    async def write_gatt_char(
        self,
        characteristic: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None:
        if data == bytes.fromhex("aa 01"):
            self.raw_notifications.append(bytes.fromhex("0105").hex())
            asyncio.create_task(self._append_later(b"S1_LYiN48D_GY".hex()))
        if data == bytes.fromhex("aa 02"):
            self.raw_notifications.append(b"V1.9.11".hex())

    async def _append_later(self, payload: str) -> None:
        await asyncio.sleep(0.01)
        self.raw_notifications.append(payload)


def test_profile_read_only_probe_queries_model_and_firmware_without_print_commands() -> None:
    raw_notifications: list[str] = []
    client = FakeReadOnlyClient(raw_notifications)
    session = ReadOnlyBleSession(
        device_id="dev_minix",
        client=client,
        services=[FF00],
        write_characteristics=[FF02],
        notify_characteristics=[FF01],
        raw_notifications=raw_notifications,
    )

    result = asyncio.run(
        ProfileReadOnlyProbe(
            profiles=[PROFILE],
            response_timeout_s=0.01,
        )(session)
    )

    assert client.writes == [
        WriteCall(FF02, bytes.fromhex("aa 01"), True),
        WriteCall(FF02, bytes.fromhex("aa 02"), True),
    ]
    assert [
        (event.operation, event.characteristic, event.payload_bytes)
        for event in session.timing_events
    ] == [
        ("write_gatt_char", FF02, 2),
        ("write_gatt_char", FF02, 2),
    ]
    assert all(event.elapsed_ms >= 0 for event in session.timing_events)
    assert result.model_response == "S1_LYiN48D_GY"
    assert result.firmware == "V1.9.11"
    assert raw_notifications == [
        b"\x02S1_LYiN48D_GY\x00".hex(),
        b"V1.9.11".hex(),
    ]


def test_profile_read_only_probe_waits_past_status_notifications_for_expected_text() -> None:
    raw_notifications: list[str] = []
    client = DelayedStatusThenTextClient(raw_notifications)
    session = ReadOnlyBleSession(
        device_id="dev_minix",
        client=client,
        services=[FF00],
        write_characteristics=[FF02],
        notify_characteristics=[FF01],
        raw_notifications=raw_notifications,
    )

    result = asyncio.run(
        ProfileReadOnlyProbe(
            profiles=[PROFILE],
            response_timeout_s=0.05,
            poll_interval_s=0.001,
        )(session)
    )

    assert result.model_response == "S1_LYiN48D_GY"
    assert result.firmware == "V1.9.11"


def test_profile_read_only_probe_skips_unknown_write_characteristic() -> None:
    raw_notifications: list[str] = []
    client = FakeReadOnlyClient(raw_notifications)
    session = ReadOnlyBleSession(
        device_id="dev_minix",
        client=client,
        services=[FF00],
        write_characteristics=["0000ffff-0000-1000-8000-00805f9b34fb"],
        notify_characteristics=[FF01],
        raw_notifications=raw_notifications,
    )

    result = asyncio.run(ProfileReadOnlyProbe(profiles=[PROFILE])(session))

    assert client.writes == []
    assert result.model_response is None
    assert result.firmware is None
