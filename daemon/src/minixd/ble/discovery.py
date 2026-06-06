from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, cast


@dataclass(frozen=True)
class BleAdvertisement:
    device_id: str
    name: str | None
    service_uuids: list[str]
    rssi: int | None = None


@dataclass(frozen=True)
class PrinterCandidate:
    device_id: str
    name: str | None
    service_uuids: list[str]
    rssi: int | None
    support_level: str
    candidate_profile_ids: list[str]
    printable: bool
    next_required_stage: str
    reason: str


@dataclass(frozen=True)
class BleTimingEvent:
    operation: str
    characteristic: str | None
    elapsed_ms: float
    payload_bytes: int | None = None


@dataclass(frozen=True)
class ReadOnlyDeviceInfo:
    model_response: str | None
    firmware: str | None
    services: list[str]
    write_characteristics: list[str]
    notify_characteristics: list[str]
    raw_notifications: list[str]
    timing_events: list[BleTimingEvent] = field(default_factory=list)


@dataclass(frozen=True)
class ReadOnlyVerification:
    status: str
    device_id: str
    profile_id: str | None
    profile_support_level: str | None
    model_response: str | None
    firmware: str | None
    printable: bool
    next_required_stage: str
    reason: str
    services: list[str]
    write_characteristics: list[str]
    notify_characteristics: list[str]
    raw_notifications: list[str]
    timing_events: list[BleTimingEvent] = field(default_factory=list)


class BleAdapter(Protocol):
    async def scan(self) -> list[BleAdvertisement]:
        """Return BLE advertisements visible to the daemon."""

    async def read_only_info(self, device_id: str) -> ReadOnlyDeviceInfo:
        """Read non-mutating identity data from a device."""


class PrinterDiscoveryError(Exception):
    """Base class for discovery failures that should be reported to callers."""


class PrinterBluetoothUnavailableError(PrinterDiscoveryError):
    """Raised when the host cannot access Bluetooth scanning or connections."""


class PrinterNotFoundError(PrinterDiscoveryError):
    """Raised when a requested BLE device is not in the adapter scan."""


class PrinterReadOnlyInfoUnavailableError(PrinterDiscoveryError):
    """Raised when the adapter cannot supply read-only device information."""


class MockBleAdapter:
    def __init__(
        self,
        *,
        advertisements: Sequence[BleAdvertisement] | None = None,
        read_only_infos: Mapping[str, ReadOnlyDeviceInfo] | None = None,
    ) -> None:
        self._advertisements = list(advertisements or [])
        self._read_only_infos = dict(read_only_infos or {})

    async def scan(self) -> list[BleAdvertisement]:
        return list(self._advertisements)

    async def read_only_info(self, device_id: str) -> ReadOnlyDeviceInfo:
        info = self._read_only_infos.get(device_id)
        if info is None:
            raise PrinterReadOnlyInfoUnavailableError(
                f"read-only information is unavailable for device: {device_id}"
            )
        return info


class PrinterDiscoveryService:
    def __init__(self, *, profiles: Sequence[dict[str, Any]], adapter: BleAdapter) -> None:
        self._profiles = list(profiles)
        self._adapter = adapter

    async def scan(self) -> list[PrinterCandidate]:
        return [self._candidate_for_advertisement(ad) for ad in await self._adapter.scan()]

    async def read_only_verify(self, device_id: str) -> ReadOnlyVerification:
        advertisement = await self._find_advertisement(device_id)
        read_only_info = await self._adapter.read_only_info(device_id)
        candidate_profiles = self._candidate_profiles_for(advertisement)
        if not candidate_profiles:
            candidate_profiles = self._candidate_profiles_for_services(read_only_info.services)

        for profile in candidate_profiles:
            if self._read_only_info_matches_profile(read_only_info, profile):
                return ReadOnlyVerification(
                    status="read_only_verified",
                    device_id=device_id,
                    profile_id=_profile_id(profile),
                    profile_support_level=_profile_support_level(profile),
                    model_response=read_only_info.model_response,
                    firmware=read_only_info.firmware,
                    printable=False,
                    next_required_stage="protocol_sanity_test",
                    reason="Model and firmware match profile; protocol sanity test required.",
                    services=_normalise_uuids(read_only_info.services),
                    write_characteristics=_normalise_uuids(read_only_info.write_characteristics),
                    notify_characteristics=_normalise_uuids(read_only_info.notify_characteristics),
                    raw_notifications=list(read_only_info.raw_notifications),
                    timing_events=list(read_only_info.timing_events),
                )

        mismatch_profile = candidate_profiles[0] if candidate_profiles else None
        return ReadOnlyVerification(
            status="read_only_mismatch",
            device_id=device_id,
            profile_id=_profile_id(mismatch_profile) if mismatch_profile is not None else None,
            profile_support_level=(
                _profile_support_level(mismatch_profile) if mismatch_profile is not None else None
            ),
            model_response=read_only_info.model_response,
            firmware=read_only_info.firmware,
            printable=False,
            next_required_stage="unsupported",
            reason="Read-only model or firmware did not match a known profile.",
            services=_normalise_uuids(read_only_info.services),
            write_characteristics=_normalise_uuids(read_only_info.write_characteristics),
            notify_characteristics=_normalise_uuids(read_only_info.notify_characteristics),
            raw_notifications=list(read_only_info.raw_notifications),
            timing_events=list(read_only_info.timing_events),
        )

    async def _find_advertisement(self, device_id: str) -> BleAdvertisement:
        for advertisement in await self._adapter.scan():
            if advertisement.device_id == device_id:
                return advertisement
        raise PrinterNotFoundError(f"printer device not found: {device_id}")

    def _candidate_for_advertisement(self, advertisement: BleAdvertisement) -> PrinterCandidate:
        candidate_profiles = self._candidate_profiles_for(advertisement)
        if not candidate_profiles:
            return PrinterCandidate(
                device_id=advertisement.device_id,
                name=advertisement.name,
                service_uuids=_normalise_uuids(advertisement.service_uuids),
                rssi=advertisement.rssi,
                support_level="unsupported",
                candidate_profile_ids=[],
                printable=False,
                next_required_stage="unsupported",
                reason="No known MiniX printer profile signal matched.",
            )

        profile_ids = [_profile_id(profile) for profile in candidate_profiles]
        service_matches = any(
            _profile_service_matches(advertisement.service_uuids, profile)
            for profile in candidate_profiles
        )
        name_matches = any(
            _profile_name_matches(advertisement.name, profile) for profile in candidate_profiles
        )
        reason = _candidate_reason(
            service_matches=service_matches,
            name_matches=name_matches,
        )
        return PrinterCandidate(
            device_id=advertisement.device_id,
            name=advertisement.name,
            service_uuids=_normalise_uuids(advertisement.service_uuids),
            rssi=advertisement.rssi,
            support_level="detected_unverified",
            candidate_profile_ids=profile_ids,
            printable=False,
            next_required_stage="read_only_verification",
            reason=reason,
        )

    def _candidate_profiles_for(self, advertisement: BleAdvertisement) -> list[dict[str, Any]]:
        service_matches = self._candidate_profiles_for_services(advertisement.service_uuids)
        name_matches = self._candidate_profiles_for_name(advertisement.name)
        return _dedupe_profiles([*service_matches, *name_matches])

    def _candidate_profiles_for_services(
        self,
        service_uuids: Sequence[str],
    ) -> list[dict[str, Any]]:
        services = set(_normalise_uuids(service_uuids))
        return [
            profile
            for profile in self._profiles
            if (service_uuid := _profile_service_uuid(profile)) is not None
            and service_uuid in services
        ]

    def _candidate_profiles_for_name(self, name: str | None) -> list[dict[str, Any]]:
        return [
            profile
            for profile in self._profiles
            if _profile_name_matches(name, profile)
        ]

    def _read_only_info_matches_profile(
        self,
        read_only_info: ReadOnlyDeviceInfo,
        profile: dict[str, Any],
    ) -> bool:
        return (
            read_only_info.model_response == _profile_model_response(profile)
            and read_only_info.firmware in _profile_observed_firmware(profile)
            and _profile_service_uuid(profile) in set(_normalise_uuids(read_only_info.services))
        )


def _normalise_uuids(values: Sequence[str]) -> list[str]:
    return [value.lower() for value in values]


def _dedupe_profiles(profiles: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for profile in profiles:
        profile_id = _profile_id(profile)
        if profile_id in seen:
            continue
        seen.add(profile_id)
        deduped.append(profile)
    return deduped


def _candidate_reason(*, service_matches: bool, name_matches: bool) -> str:
    if service_matches and name_matches:
        return "Service UUID and name match; model query required."
    if service_matches:
        return "Service UUID matches; model query required."
    return "Name matches; model query required."


def _profile_ble(profile: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("ble")
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _profile_id(profile: dict[str, Any]) -> str:
    value = profile.get("id")
    if isinstance(value, str):
        return value
    return ""


def _profile_support_level(profile: dict[str, Any]) -> str | None:
    value = profile.get("supportLevel")
    if isinstance(value, str):
        return value
    return None


def _profile_service_uuid(profile: dict[str, Any]) -> str | None:
    value = _profile_ble(profile).get("serviceUuid")
    if isinstance(value, str):
        return value.lower()
    return None


def _profile_service_matches(service_uuids: Sequence[str], profile: dict[str, Any]) -> bool:
    service_uuid = _profile_service_uuid(profile)
    return service_uuid is not None and service_uuid in set(_normalise_uuids(service_uuids))


def _profile_model_response(profile: dict[str, Any]) -> str | None:
    value = profile.get("modelResponse")
    if isinstance(value, str):
        return value
    return None


def _profile_observed_firmware(profile: dict[str, Any]) -> set[str]:
    value = profile.get("observedFirmware")
    if isinstance(value, list):
        return {firmware for firmware in value if isinstance(firmware, str)}
    return set()


def _profile_name_matches(name: str | None, profile: dict[str, Any]) -> bool:
    if name is None:
        return False
    value = profile.get("namePrefixes")
    if not isinstance(value, list):
        return False
    return any(isinstance(prefix, str) and name.startswith(prefix) for prefix in value)
