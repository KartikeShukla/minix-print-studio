from __future__ import annotations

import time
from collections.abc import Awaitable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

from bleak.exc import BleakBluetoothNotAvailableError

from minixd.ble.discovery import (
    BleAdvertisement,
    BleTimingEvent,
    PrinterBluetoothUnavailableError,
    PrinterNotFoundError,
    ReadOnlyDeviceInfo,
)


class ScannerDiscover(Protocol):
    def __call__(
        self,
        timeout: float,
        *,
        return_adv: Literal[True],
        service_uuids: list[str],
    ) -> Awaitable[Mapping[str, tuple[object, object]]]: ...


class BleakClientLike(Protocol):
    services: object

    async def __aenter__(self) -> BleakClientLike: ...

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...

    async def start_notify(
        self,
        characteristic: str,
        callback: object,
    ) -> None: ...

    async def stop_notify(self, characteristic: str) -> None: ...

    async def write_gatt_char(
        self,
        characteristic: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None: ...


class ClientFactory(Protocol):
    def __call__(self, device: object, services: list[str]) -> BleakClientLike: ...


@dataclass
class ReadOnlyBleSession:
    device_id: str
    client: BleakClientLike
    services: list[str]
    write_characteristics: list[str]
    notify_characteristics: list[str]
    raw_notifications: list[str] = field(default_factory=list)
    timing_events: list[BleTimingEvent] = field(default_factory=list)


@dataclass(frozen=True)
class ReadOnlyProbeResult:
    model_response: str | None
    firmware: str | None
    raw_notifications: list[str] = field(default_factory=list)


class ReadOnlyProbe(Protocol):
    async def __call__(self, session: ReadOnlyBleSession) -> ReadOnlyProbeResult: ...


class BleakBleAdapter:
    def __init__(
        self,
        *,
        scanner_discover: ScannerDiscover | None = None,
        client_factory: ClientFactory | None = None,
        scan_timeout_s: float = 5.0,
        service_uuids: Sequence[str] = (),
        read_only_probe: ReadOnlyProbe | None = None,
    ) -> None:
        self._scanner_discover = scanner_discover or _default_scanner_discover
        self._client_factory = client_factory or _default_client_factory
        self._scan_timeout_s = scan_timeout_s
        self._service_uuids = _normalise_uuids(service_uuids)
        self._read_only_probe = read_only_probe or _no_read_only_probe
        self._devices_by_id: dict[str, object] = {}

    async def scan(self) -> list[BleAdvertisement]:
        try:
            discovered = await self._scanner_discover(
                self._scan_timeout_s,
                return_adv=True,
                service_uuids=list(self._service_uuids),
            )
        except BleakBluetoothNotAvailableError as exc:
            raise PrinterBluetoothUnavailableError(
                f"Bluetooth unavailable: {_exception_message(exc)}"
            ) from exc
        advertisements: list[BleAdvertisement] = []
        self._devices_by_id = {}
        for device_id, (device, advertisement_data) in discovered.items():
            self._devices_by_id[device_id] = device
            advertisements.append(
                BleAdvertisement(
                    device_id=device_id,
                    name=_advertisement_name(device, advertisement_data),
                    service_uuids=_normalise_uuids(
                        _attribute_list(advertisement_data, "service_uuids")
                    ),
                    rssi=_attribute_int(advertisement_data, "rssi"),
                )
            )
        return advertisements

    async def read_only_info(self, device_id: str) -> ReadOnlyDeviceInfo:
        device = await self._device_for(device_id)
        client = self._client_factory(device, list(self._service_uuids))

        async with client as connected_client:
            services = _service_uuids(connected_client.services)
            write_characteristics = _characteristic_uuids(
                connected_client.services,
                accepted_properties={"write", "write-with-response", "write-without-response"},
            )
            notify_characteristics = _characteristic_uuids(
                connected_client.services,
                accepted_properties={"notify", "indicate"},
            )
            raw_notifications: list[str] = []
            timing_events: list[BleTimingEvent] = []
            started_notify: list[str] = []

            def capture_notification(sender: object, data: bytes | bytearray) -> None:
                raw_notifications.append(bytes(data).hex())
                timing_events.append(
                    BleTimingEvent(
                        operation="notification",
                        characteristic=str(sender),
                        elapsed_ms=0,
                        payload_bytes=len(data),
                    )
                )

            try:
                for characteristic in notify_characteristics:
                    timing_events.append(
                        BleTimingEvent(
                            operation="start_notify",
                            characteristic=characteristic,
                            elapsed_ms=0,
                        )
                    )
                    await connected_client.start_notify(characteristic, capture_notification)
                    started_notify.append(characteristic)

                session = ReadOnlyBleSession(
                    device_id=device_id,
                    client=connected_client,
                    services=services,
                    write_characteristics=write_characteristics,
                    notify_characteristics=notify_characteristics,
                    raw_notifications=raw_notifications,
                    timing_events=timing_events,
                )
                result = await self._read_only_probe(session)
            finally:
                for characteristic in started_notify:
                    start = time.perf_counter()
                    await connected_client.stop_notify(characteristic)
                    timing_events.append(
                        BleTimingEvent(
                            operation="stop_notify",
                            characteristic=characteristic,
                            elapsed_ms=_elapsed_ms(start),
                        )
                    )

            return ReadOnlyDeviceInfo(
                model_response=result.model_response,
                firmware=result.firmware,
                services=services,
                write_characteristics=write_characteristics,
                notify_characteristics=notify_characteristics,
                raw_notifications=[*raw_notifications, *result.raw_notifications],
                timing_events=timing_events,
            )

    async def _device_for(self, device_id: str) -> object:
        device = self._devices_by_id.get(device_id)
        if device is not None:
            return device

        await self.scan()
        device = self._devices_by_id.get(device_id)
        if device is None:
            raise PrinterNotFoundError(f"printer device not found: {device_id}")
        return device


async def _default_scanner_discover(
    timeout: float,
    *,
    return_adv: Literal[True],
    service_uuids: list[str],
) -> Mapping[str, tuple[object, object]]:
    from bleak import BleakScanner

    discovered = await BleakScanner.discover(
        timeout=timeout,
        return_adv=return_adv,
        service_uuids=service_uuids,
    )
    return cast(Mapping[str, tuple[object, object]], discovered)


def _default_client_factory(device: object, services: list[str]) -> BleakClientLike:
    from bleak import BleakClient

    return cast(BleakClientLike, BleakClient(cast(Any, device), services=services))


def _elapsed_ms(start: float) -> float:
    return max((time.perf_counter() - start) * 1000, 0)


def _exception_message(exc: Exception) -> str:
    if exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return str(exc)


async def _no_read_only_probe(session: ReadOnlyBleSession) -> ReadOnlyProbeResult:
    return ReadOnlyProbeResult(model_response=None, firmware=None)


def _advertisement_name(device: object, advertisement_data: object) -> str | None:
    local_name = _attribute_str(advertisement_data, "local_name")
    if local_name:
        return local_name
    return _attribute_str(device, "name")


def _service_uuids(services: object) -> list[str]:
    return [
        uuid.lower()
        for item in _iter_objects(services)
        if (uuid := _attribute_str(item, "uuid")) is not None
    ]


def _characteristic_uuids(
    services: object,
    *,
    accepted_properties: set[str],
) -> list[str]:
    characteristic_uuids: list[str] = []
    for service in _iter_objects(services):
        for characteristic in _iter_objects(_attribute_object(service, "characteristics")):
            properties = {
                value.lower()
                for value in _attribute_list(characteristic, "properties")
            }
            if properties.intersection(accepted_properties):
                uuid = _attribute_str(characteristic, "uuid")
                if uuid is not None:
                    characteristic_uuids.append(uuid.lower())
    return characteristic_uuids


def _attribute_object(value: object, name: str) -> object:
    return getattr(value, name, None)


def _attribute_str(value: object, name: str) -> str | None:
    raw = getattr(value, name, None)
    if isinstance(raw, str):
        return raw
    return None


def _attribute_int(value: object, name: str) -> int | None:
    raw = getattr(value, name, None)
    if isinstance(raw, int):
        return raw
    return None


def _attribute_list(value: object, name: str) -> list[str]:
    raw = getattr(value, name, None)
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    if isinstance(raw, tuple):
        return [item for item in raw if isinstance(item, str)]
    return []


def _iter_objects(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return list(value.values())
    if isinstance(value, Iterable) and not isinstance(value, str | bytes | bytearray):
        return list(value)
    return []


def _normalise_uuids(values: Sequence[str]) -> list[str]:
    return [value.lower() for value in values]
