import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from minixd.printing.planner import create_print_plan
from minixd.printing.transport import BleakPrintTransport
from minixd.protocol.aiyin import (
    build_enable_mode_command,
    build_feed_form_command,
    build_raster_command,
    build_set_density_command,
    build_set_paper_mode_command,
    build_stop_mode_command,
    build_wake_command,
)

PROFILE_PATH = Path("profiles/seznik-minix-s1-lyin48d-gy/profile.json")
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
    def __iter__(self) -> Any:
        return iter(
            [
                FakeService(
                    uuid=FF00,
                    characteristics=[
                        FakeCharacteristic(uuid=FF02, properties=["write-with-response"]),
                        FakeCharacteristic(uuid=FF01, properties=["notify"]),
                        FakeCharacteristic(uuid=FF03, properties=["notify"]),
                    ],
                )
            ]
        )


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

    async def stop_notify(self, characteristic: str) -> None:
        self.events.append(("stop_notify", characteristic))

    async def write_gatt_char(
        self,
        characteristic: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None:
        self.events.append(("write", characteristic, bytes(data), response))


def load_profile() -> dict[str, object]:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile["ble"]["defaultChunkSize"] = 40
    profile["ble"]["defaultInterChunkDelayMs"] = 3
    return profile


def test_bleak_print_transport_sends_aiyin_print_sequence_in_profile_chunks() -> None:
    events: list[object] = []
    sleeps: list[float] = []
    fake_device = FakeDevice(address="dev_minix", name="Seznik MiniX_0194_LE")
    profile = load_profile()
    content_raster = bytes(range(96))
    plan_package = create_print_plan(
        job_id="job_transport",
        preview_id="prev_transport",
        document_hash="sha256:document",
        content_raster=content_raster,
        content_height_dots=2,
        profile=profile,
        paper_mode="gap_label",
        density="medium",
    )

    async def discover(
        timeout: float,
        *,
        return_adv: bool,
        service_uuids: list[str],
    ) -> dict[str, tuple[FakeDevice, FakeAdvertisementData]]:
        events.append(("scan", timeout, return_adv, service_uuids))
        return {
            "dev_minix": (
                fake_device,
                FakeAdvertisementData(
                    local_name="Seznik MiniX_0194_LE",
                    service_uuids=[FF00],
                    rssi=-45,
                ),
            )
        }

    def client_factory(device: object, services: list[str]) -> FakeBleakClient:
        assert device is fake_device
        assert services == [FF00]
        return FakeBleakClient(events)

    async def sleep(delay_s: float) -> None:
        sleeps.append(delay_s)

    transport = BleakPrintTransport(
        scanner_discover=discover,
        client_factory=client_factory,
        sleep=sleep,
        scan_timeout_s=0.1,
        service_uuids=[FF00],
    )

    result = transport.print_plan(
        device_id="dev_minix",
        profile=profile,
        plan_package=plan_package,
    )

    writes = [
        event
        for event in events
        if isinstance(event, tuple) and event[0] == "write"
    ]
    raster_command = build_raster_command(
        width_dots=384,
        height_dots=2,
        packed_raster=content_raster,
    )

    assert events[:4] == [
        ("scan", 0.1, True, [FF00]),
        "connect",
        ("start_notify", FF01),
        ("start_notify", FF03),
    ]
    assert writes[:4] == [
        ("write", FF02, build_wake_command(), True),
        ("write", FF02, build_set_density_command("medium"), True),
        ("write", FF02, build_set_paper_mode_command("gap_label"), True),
        ("write", FF02, build_enable_mode_command(), True),
    ]
    assert [event[2] for event in writes[4:7]] == [
        raster_command[:40],
        raster_command[40:80],
        raster_command[80:],
    ]
    assert writes[7:] == [
        ("write", FF02, build_feed_form_command(), True),
        ("write", FF02, build_stop_mode_command(), True),
    ]
    assert events[-3:] == [("stop_notify", FF01), ("stop_notify", FF03), "disconnect"]
    assert sleeps == [0.003, 0.003]
    assert result.bands_sent == 1
    assert result.rows_sent == 2
    assert result.raster_bytes_sent == 96
    assert result.protocol_bytes_sent == (
        len(build_wake_command())
        + len(build_set_density_command("medium"))
        + len(build_set_paper_mode_command("gap_label"))
        + len(build_enable_mode_command())
        + len(raster_command)
        + len(build_feed_form_command())
        + len(build_stop_mode_command())
    )


def test_bleak_print_transport_falls_back_to_unfiltered_scan_for_name_only_advertising() -> None:
    calls: list[list[str]] = []
    events: list[object] = []
    fake_device = FakeDevice(address="dev_minix", name="Seznik MiniX_0194_LE")
    profile = load_profile()
    plan_package = create_print_plan(
        job_id="job_transport",
        preview_id="prev_transport",
        document_hash="sha256:document",
        content_raster=b"\x00" * 96,
        content_height_dots=2,
        profile=profile,
        paper_mode="gap_label",
        density="medium",
    )

    async def discover(
        timeout: float,
        *,
        return_adv: bool,
        service_uuids: list[str],
    ) -> dict[str, tuple[FakeDevice, FakeAdvertisementData]]:
        calls.append(service_uuids)
        if service_uuids:
            return {}
        return {
            "dev_minix": (
                fake_device,
                FakeAdvertisementData(
                    local_name="Seznik MiniX_0194_LE",
                    service_uuids=[],
                    rssi=-55,
                ),
            )
        }

    def client_factory(device: object, services: list[str]) -> FakeBleakClient:
        assert device is fake_device
        return FakeBleakClient(events)

    async def sleep(delay_s: float) -> None:
        pass

    transport = BleakPrintTransport(
        scanner_discover=discover,
        client_factory=client_factory,
        sleep=sleep,
        scan_timeout_s=0.1,
        service_uuids=[FF00],
    )

    result = transport.print_plan(
        device_id="dev_minix",
        profile=profile,
        plan_package=plan_package,
    )

    assert calls == [[FF00], []]
    assert result.raster_bytes_sent == 96
