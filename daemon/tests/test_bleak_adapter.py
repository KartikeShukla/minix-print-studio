import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from bleak.exc import BleakBluetoothNotAvailableError, BleakBluetoothNotAvailableReason

from minixd.ble.bleak_adapter import BleakBleAdapter, ReadOnlyProbeResult
from minixd.ble.discovery import PrinterDiscoveryError

FF00 = "0000ff00-0000-1000-8000-00805f9b34fb"
FF01 = "0000ff01-0000-1000-8000-00805f9b34fb"
FF02 = "0000ff02-0000-1000-8000-00805f9b34fb"
FF03 = "0000ff03-0000-1000-8000-00805f9b34fb"


@dataclass(frozen=True)
class FakeDevice:
    address: str
    name: str | None = None


@dataclass(frozen=True)
class FakeAdvertisementData:
    local_name: str | None
    service_uuids: list[str]
    rssi: int | None


@dataclass(frozen=True)
class FakeCharacteristic:
    uuid: str
    properties: list[str]


@dataclass(frozen=True)
class FakeService:
    uuid: str
    characteristics: list[FakeCharacteristic]


class FakeServices:
    def __init__(self) -> None:
        self._services = [
            FakeService(
                uuid=FF00,
                characteristics=[
                    FakeCharacteristic(uuid=FF02, properties=["write", "write-with-response"]),
                    FakeCharacteristic(uuid=FF01, properties=["notify"]),
                    FakeCharacteristic(uuid=FF03, properties=["notify"]),
                ],
            )
        ]

    def __iter__(self) -> Any:
        return iter(self._services)


class FakeBleakClient:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.services = FakeServices()

    async def __aenter__(self) -> "FakeBleakClient":
        self.events.append("connect")
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.events.append("disconnect")

    async def start_notify(
        self,
        characteristic: str,
        callback: Callable[[str, bytes], None],
    ) -> None:
        self.events.append(("start_notify", characteristic))
        callback(characteristic, bytes.fromhex("aa55"))

    async def stop_notify(self, characteristic: str) -> None:
        self.events.append(("stop_notify", characteristic))


def test_bleak_scan_maps_advertisement_data_to_daemon_advertisements() -> None:
    calls: list[dict[str, object]] = []

    async def discover(
        timeout: float,
        *,
        return_adv: bool,
        service_uuids: list[str],
    ) -> dict[str, tuple[FakeDevice, FakeAdvertisementData]]:
        calls.append(
            {
                "timeout": timeout,
                "return_adv": return_adv,
                "service_uuids": service_uuids,
            }
        )
        return {
            "dev_minix": (
                FakeDevice(address="dev_minix", name="Fallback Name"),
                FakeAdvertisementData(
                    local_name="Seznik MiniX_0194_LE",
                    service_uuids=[FF00.upper()],
                    rssi=-47,
                ),
            )
        }

    adapter = BleakBleAdapter(
        scanner_discover=discover,
        client_factory=_unused_client_factory,
        scan_timeout_s=2.5,
        service_uuids=[FF00],
    )

    advertisements = asyncio.run(adapter.scan())

    assert calls == [{"timeout": 2.5, "return_adv": True, "service_uuids": [FF00]}]
    assert advertisements[0].device_id == "dev_minix"
    assert advertisements[0].name == "Seznik MiniX_0194_LE"
    assert advertisements[0].service_uuids == [FF00]
    assert advertisements[0].rssi == -47


def test_bleak_scan_reports_bluetooth_unavailable() -> None:
    async def discover(
        timeout: float,
        *,
        return_adv: bool,
        service_uuids: list[str],
    ) -> dict[str, tuple[FakeDevice, FakeAdvertisementData]]:
        raise BleakBluetoothNotAvailableError(
            "Bluetooth is unsupported",
            BleakBluetoothNotAvailableReason.NO_BLUETOOTH,
        )

    adapter = BleakBleAdapter(
        scanner_discover=discover,
        client_factory=_unused_client_factory,
        scan_timeout_s=0.1,
        service_uuids=[FF00],
    )

    with pytest.raises(PrinterDiscoveryError, match="Bluetooth unavailable"):
        asyncio.run(adapter.scan())


def test_bleak_read_only_info_connects_subscribes_probes_and_disconnects() -> None:
    events: list[object] = []
    fake_device = FakeDevice(address="dev_minix", name="Seznik MiniX_0194_LE")

    async def discover(
        timeout: float,
        *,
        return_adv: bool,
        service_uuids: list[str],
    ) -> dict[str, tuple[FakeDevice, FakeAdvertisementData]]:
        return {
            "dev_minix": (
                fake_device,
                FakeAdvertisementData(
                    local_name="Seznik MiniX_0194_LE",
                    service_uuids=[FF00],
                    rssi=-49,
                ),
            )
        }

    def client_factory(device: object, services: list[str]) -> FakeBleakClient:
        assert device is fake_device
        assert services == [FF00]
        return FakeBleakClient(events)

    async def probe(session: Any) -> ReadOnlyProbeResult:
        events.append(("probe", session.device_id))
        assert session.services == [FF00]
        assert session.write_characteristics == [FF02]
        assert session.notify_characteristics == [FF01, FF03]
        assert session.raw_notifications == ["aa55", "aa55"]
        return ReadOnlyProbeResult(
            model_response="S1_LYiN48D_GY",
            firmware="V1.9.11",
            raw_notifications=["probe:ok"],
        )

    adapter = BleakBleAdapter(
        scanner_discover=discover,
        client_factory=client_factory,
        scan_timeout_s=0.1,
        service_uuids=[FF00],
        read_only_probe=probe,
    )

    info = asyncio.run(adapter.read_only_info("dev_minix"))

    assert info.model_response == "S1_LYiN48D_GY"
    assert info.firmware == "V1.9.11"
    assert info.services == [FF00]
    assert info.write_characteristics == [FF02]
    assert info.notify_characteristics == [FF01, FF03]
    assert info.raw_notifications == ["aa55", "aa55", "probe:ok"]
    assert [
        (event.operation, event.characteristic, event.payload_bytes)
        for event in info.timing_events
    ] == [
        ("start_notify", FF01, None),
        ("notification", FF01, 2),
        ("start_notify", FF03, None),
        ("notification", FF03, 2),
        ("stop_notify", FF01, None),
        ("stop_notify", FF03, None),
    ]
    assert all(event.elapsed_ms >= 0 for event in info.timing_events)
    assert events == [
        "connect",
        ("start_notify", FF01),
        ("start_notify", FF03),
        ("probe", "dev_minix"),
        ("stop_notify", FF01),
        ("stop_notify", FF03),
        "disconnect",
    ]


def _unused_client_factory(device: object, services: list[str]) -> object:
    raise AssertionError("client factory should not be used during scan")
