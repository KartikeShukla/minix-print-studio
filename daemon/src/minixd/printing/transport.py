from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from bleak.exc import BleakBluetoothNotAvailableError

from minixd.printing.planner import PrintPlanPackage
from minixd.protocol.aiyin import (
    build_enable_mode_command,
    build_feed_form_command,
    build_raster_command,
    build_set_density_command,
    build_set_paper_mode_command,
    build_stop_mode_command,
    build_wake_command,
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


class PrintTransport(Protocol):
    def print_plan(
        self,
        *,
        device_id: str,
        profile: dict[str, object],
        plan_package: PrintPlanPackage,
    ) -> PrintTransportResult: ...


@dataclass(frozen=True)
class PrintTransportResult:
    bands_sent: int
    rows_sent: int
    raster_bytes_sent: int
    protocol_bytes_sent: int
    notification_count: int


class PrintTransportError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        bands_sent: int = 0,
        rows_sent: int = 0,
        raster_bytes_sent: int = 0,
        protocol_bytes_sent: int = 0,
        notification_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.bands_sent = bands_sent
        self.rows_sent = rows_sent
        self.raster_bytes_sent = raster_bytes_sent
        self.protocol_bytes_sent = protocol_bytes_sent
        self.notification_count = notification_count


@dataclass
class _TransferCounters:
    bands_sent: int = 0
    rows_sent: int = 0
    raster_bytes_sent: int = 0
    protocol_bytes_sent: int = 0
    notification_count: int = 0

    def result(self) -> PrintTransportResult:
        return PrintTransportResult(
            bands_sent=self.bands_sent,
            rows_sent=self.rows_sent,
            raster_bytes_sent=self.raster_bytes_sent,
            protocol_bytes_sent=self.protocol_bytes_sent,
            notification_count=self.notification_count,
        )

    def error(self, message: str) -> PrintTransportError:
        return PrintTransportError(
            message,
            bands_sent=self.bands_sent,
            rows_sent=self.rows_sent,
            raster_bytes_sent=self.raster_bytes_sent,
            protocol_bytes_sent=self.protocol_bytes_sent,
            notification_count=self.notification_count,
        )


type AsyncSleep = Callable[[float], Awaitable[None]]


class BleakPrintTransport:
    def __init__(
        self,
        *,
        scanner_discover: ScannerDiscover | None = None,
        client_factory: ClientFactory | None = None,
        sleep: AsyncSleep | None = None,
        scan_timeout_s: float = 5.0,
        service_uuids: Sequence[str] = (),
    ) -> None:
        self._scanner_discover = scanner_discover or _default_scanner_discover
        self._client_factory = client_factory or _default_client_factory
        self._sleep = sleep or asyncio.sleep
        self._scan_timeout_s = scan_timeout_s
        self._service_uuids = _normalise_uuids(service_uuids)

    def print_plan(
        self,
        *,
        device_id: str,
        profile: dict[str, object],
        plan_package: PrintPlanPackage,
    ) -> PrintTransportResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self._print_plan(
                    device_id=device_id,
                    profile=profile,
                    plan_package=plan_package,
                )
            )
        raise PrintTransportError("physical print transport cannot run inside an active event loop")

    async def _print_plan(
        self,
        *,
        device_id: str,
        profile: dict[str, object],
        plan_package: PrintPlanPackage,
    ) -> PrintTransportResult:
        counters = _TransferCounters()
        service_uuids = _profile_service_uuids(profile) or self._service_uuids
        write_characteristic = _required_profile_string(profile, "ble", "writeCharUuid")
        notify_characteristics = _profile_notify_characteristics(profile)
        chunk_size = _profile_int(profile, "ble", "defaultChunkSize", default=90)
        inter_chunk_delay_s = _profile_int(
            profile,
            "ble",
            "defaultInterChunkDelayMs",
            default=25,
        ) / 1000
        write_with_response = _profile_bool(profile, "ble", "writeWithResponse", default=True)

        try:
            discovered = await self._scanner_discover(
                self._scan_timeout_s,
                return_adv=True,
                service_uuids=service_uuids,
            )
            if not discovered and service_uuids:
                discovered = await self._scanner_discover(
                    self._scan_timeout_s,
                    return_adv=True,
                    service_uuids=[],
                )
        except BleakBluetoothNotAvailableError as exc:
            raise counters.error(f"Bluetooth unavailable: {_exception_message(exc)}") from exc

        device_tuple = discovered.get(device_id)
        if device_tuple is None:
            raise counters.error(f"printer device not found: {device_id}")
        device = device_tuple[0]
        client = self._client_factory(device, service_uuids)
        started_notify: list[str] = []

        async with client as connected_client:
            try:
                available_writes = set(
                    _characteristic_uuids(
                        connected_client.services,
                        accepted_properties={
                            "write",
                            "write-with-response",
                            "write-without-response",
                        },
                    )
                )
                if write_characteristic not in available_writes:
                    raise counters.error(
                        f"printer write characteristic unavailable: {write_characteristic}"
                    )
                available_notify = set(
                    _characteristic_uuids(
                        connected_client.services,
                        accepted_properties={"notify", "indicate"},
                    )
                )

                def capture_notification(sender: object, data: bytes | bytearray) -> None:
                    counters.notification_count += 1

                for characteristic in notify_characteristics:
                    if characteristic not in available_notify:
                        continue
                    await connected_client.start_notify(characteristic, capture_notification)
                    started_notify.append(characteristic)

                await self._write_chunked(
                    connected_client,
                    write_characteristic,
                    build_wake_command(),
                    response=write_with_response,
                    chunk_size=chunk_size,
                    inter_chunk_delay_s=inter_chunk_delay_s,
                    counters=counters,
                )
                await self._write_chunked(
                    connected_client,
                    write_characteristic,
                    build_set_density_command(plan_package.plan.density),
                    response=write_with_response,
                    chunk_size=chunk_size,
                    inter_chunk_delay_s=inter_chunk_delay_s,
                    counters=counters,
                )
                await self._write_chunked(
                    connected_client,
                    write_characteristic,
                    build_set_paper_mode_command(plan_package.plan.paper_mode),
                    response=write_with_response,
                    chunk_size=chunk_size,
                    inter_chunk_delay_s=inter_chunk_delay_s,
                    counters=counters,
                )
                await self._write_chunked(
                    connected_client,
                    write_characteristic,
                    build_enable_mode_command(),
                    response=write_with_response,
                    chunk_size=chunk_size,
                    inter_chunk_delay_s=inter_chunk_delay_s,
                    counters=counters,
                )

                for band in plan_package.bands:
                    command = build_raster_command(
                        width_dots=plan_package.plan.width_dots,
                        height_dots=band.height_dots,
                        packed_raster=band.raster,
                    )
                    await self._write_chunked(
                        connected_client,
                        write_characteristic,
                        command,
                        response=write_with_response,
                        chunk_size=chunk_size,
                        inter_chunk_delay_s=inter_chunk_delay_s,
                        counters=counters,
                    )
                    counters.bands_sent += 1
                    counters.rows_sent += band.height_dots
                    counters.raster_bytes_sent += band.raster_byte_length
                    if band.cooldown_after_ms > 0:
                        await self._sleep(band.cooldown_after_ms / 1000)

                await self._write_chunked(
                    connected_client,
                    write_characteristic,
                    build_feed_form_command(),
                    response=write_with_response,
                    chunk_size=chunk_size,
                    inter_chunk_delay_s=inter_chunk_delay_s,
                    counters=counters,
                )
                await self._write_chunked(
                    connected_client,
                    write_characteristic,
                    build_stop_mode_command(),
                    response=write_with_response,
                    chunk_size=chunk_size,
                    inter_chunk_delay_s=inter_chunk_delay_s,
                    counters=counters,
                )
            except PrintTransportError:
                raise
            except Exception as exc:
                raise counters.error(
                    f"physical print transport failed: {_exception_message(exc)}"
                ) from exc
            finally:
                for characteristic in started_notify:
                    try:
                        await connected_client.stop_notify(characteristic)
                    except Exception:
                        pass

        return counters.result()

    async def _write_chunked(
        self,
        client: BleakClientLike,
        characteristic: str,
        payload: bytes,
        *,
        response: bool,
        chunk_size: int,
        inter_chunk_delay_s: float,
        counters: _TransferCounters,
    ) -> None:
        if chunk_size <= 0:
            raise counters.error("profile BLE chunk size must be positive")
        chunks = [
            payload[index : index + chunk_size]
            for index in range(0, len(payload), chunk_size)
        ] or [b""]
        for index, chunk in enumerate(chunks):
            await client.write_gatt_char(characteristic, chunk, response=response)
            counters.protocol_bytes_sent += len(chunk)
            if inter_chunk_delay_s > 0 and index < len(chunks) - 1:
                await self._sleep(inter_chunk_delay_s)


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


def _profile_service_uuids(profile: dict[str, object]) -> list[str]:
    value = _profile_ble(profile).get("serviceUuid")
    return [value.lower()] if isinstance(value, str) else []


def _profile_notify_characteristics(profile: dict[str, object]) -> list[str]:
    value = _profile_ble(profile).get("notifyCharUuids")
    if isinstance(value, list):
        return [item.lower() for item in value if isinstance(item, str)]
    return []


def _required_profile_string(profile: dict[str, object], section: str, key: str) -> str:
    value = _profile_section(profile, section).get(key)
    if not isinstance(value, str) or not value:
        raise PrintTransportError(f"profile missing required field: {section}.{key}")
    return value.lower()


def _profile_int(
    profile: dict[str, object],
    section: str,
    key: str,
    *,
    default: int,
) -> int:
    value = _profile_section(profile, section).get(key)
    return value if isinstance(value, int) else default


def _profile_bool(
    profile: dict[str, object],
    section: str,
    key: str,
    *,
    default: bool,
) -> bool:
    value = _profile_section(profile, section).get(key)
    return value if isinstance(value, bool) else default


def _profile_ble(profile: dict[str, object]) -> dict[str, object]:
    return _profile_section(profile, "ble")


def _profile_section(profile: dict[str, object], section: str) -> dict[str, object]:
    value = profile.get(section)
    if isinstance(value, dict):
        return cast(dict[str, object], value)
    return {}


def _attribute_object(value: object, name: str) -> object:
    return getattr(value, name, None)


def _attribute_str(value: object, name: str) -> str | None:
    raw = getattr(value, name, None)
    if isinstance(raw, str):
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


def _exception_message(exc: Exception) -> str:
    if exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return str(exc)
