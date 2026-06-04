from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

from minixd.ble.bleak_adapter import ReadOnlyBleSession, ReadOnlyProbeResult
from minixd.protocol.aiyin import build_info_command


@dataclass(frozen=True)
class ProfileReadOnlyProbe:
    profiles: Sequence[dict[str, Any]]
    response_timeout_s: float = 0.75
    poll_interval_s: float = 0.01

    async def __call__(self, session: ReadOnlyBleSession) -> ReadOnlyProbeResult:
        profile = _matching_profile(self.profiles, session.services)
        if profile is None:
            return ReadOnlyProbeResult(model_response=None, firmware=None)

        write_characteristic = _profile_write_characteristic(profile)
        if write_characteristic is None:
            return ReadOnlyProbeResult(model_response=None, firmware=None)
        if write_characteristic not in set(_normalise_uuids(session.write_characteristics)):
            return ReadOnlyProbeResult(model_response=None, firmware=None)

        write_with_response = _profile_write_with_response(profile)
        model_command = _profile_read_only_command(profile, "model")
        firmware_command = _profile_read_only_command(profile, "firmware")
        if model_command is None or firmware_command is None:
            return ReadOnlyProbeResult(model_response=None, firmware=None)

        model_response = await self._query_text(
            session,
            write_characteristic,
            model_command,
            expected_values=_profile_expected_models(profile),
            response=write_with_response,
        )
        firmware = await self._query_text(
            session,
            write_characteristic,
            firmware_command,
            expected_values=_profile_observed_firmware(profile),
            response=write_with_response,
        )
        return ReadOnlyProbeResult(model_response=model_response, firmware=firmware)

    async def _query_text(
        self,
        session: ReadOnlyBleSession,
        characteristic: str,
        command: bytes,
        *,
        expected_values: Sequence[str],
        response: bool,
    ) -> str | None:
        start_index = len(session.raw_notifications)
        await session.client.write_gatt_char(
            characteristic,
            command,
            response=response,
        )
        notifications = await self._wait_for_notifications(session.raw_notifications, start_index)
        return _extract_expected_text(notifications, expected_values)

    async def _wait_for_notifications(
        self,
        raw_notifications: list[str],
        start_index: int,
    ) -> list[str]:
        deadline = time.monotonic() + self.response_timeout_s
        while len(raw_notifications) == start_index and time.monotonic() < deadline:
            await asyncio.sleep(self.poll_interval_s)
        return raw_notifications[start_index:]


def _matching_profile(
    profiles: Sequence[dict[str, Any]],
    services: Sequence[str],
) -> dict[str, Any] | None:
    service_set = set(_normalise_uuids(services))
    for profile in profiles:
        service_uuid = _profile_service_uuid(profile)
        if service_uuid is not None and service_uuid in service_set:
            return profile
    return None


def _profile_ble(profile: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("ble")
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _profile_service_uuid(profile: dict[str, Any]) -> str | None:
    value = _profile_ble(profile).get("serviceUuid")
    if isinstance(value, str):
        return value.lower()
    return None


def _profile_write_characteristic(profile: dict[str, Any]) -> str | None:
    value = _profile_ble(profile).get("writeCharUuid")
    if isinstance(value, str):
        return value.lower()
    return None


def _profile_write_with_response(profile: dict[str, Any]) -> bool:
    value = _profile_ble(profile).get("writeWithResponse")
    return value if isinstance(value, bool) else True


def _profile_read_only(profile: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("readOnly")
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _profile_read_only_command(profile: dict[str, Any], kind: str) -> bytes | None:
    key = f"{kind}CommandHex"
    value = _profile_read_only(profile).get(key)
    if isinstance(value, str):
        try:
            return bytes.fromhex(value)
        except ValueError:
            return None

    try:
        return build_info_command(kind)
    except ValueError:
        return None


def _profile_expected_models(profile: dict[str, Any]) -> list[str]:
    value = profile.get("modelResponse")
    return [value] if isinstance(value, str) else []


def _profile_observed_firmware(profile: dict[str, Any]) -> list[str]:
    value = profile.get("observedFirmware")
    if isinstance(value, list):
        return [firmware for firmware in value if isinstance(firmware, str)]
    return []


def _extract_expected_text(
    raw_notifications: Sequence[str],
    expected_values: Sequence[str],
) -> str | None:
    decoded_payloads = [_decode_ascii_notification(raw) for raw in raw_notifications]
    for expected in expected_values:
        for payload in decoded_payloads:
            if payload is not None and expected in payload:
                return expected
    return next((payload for payload in decoded_payloads if payload), None)


def _decode_ascii_notification(raw: str) -> str | None:
    try:
        data = bytes.fromhex(raw)
    except ValueError:
        return None
    text = data.decode("ascii", errors="ignore")
    printable = "".join(character for character in text if character.isprintable())
    return printable.strip() or None


def _normalise_uuids(values: Sequence[str]) -> list[str]:
    return [value.lower() for value in values]
