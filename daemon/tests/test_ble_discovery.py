import asyncio

from minixd.app import load_profiles
from minixd.ble.discovery import (
    BleAdvertisement,
    MockBleAdapter,
    PrinterDiscoveryService,
    ReadOnlyDeviceInfo,
)

FF00 = "0000ff00-0000-1000-8000-00805f9b34fb"


def test_scan_classifies_known_ff00_name_as_detected_unverified_not_printable() -> None:
    service = PrinterDiscoveryService(
        profiles=load_profiles(),
        adapter=MockBleAdapter(
            advertisements=[
                BleAdvertisement(
                    device_id="dev_minix",
                    name="Seznik MiniX_0194_LE",
                    service_uuids=[FF00],
                    rssi=-48,
                )
            ],
        ),
    )

    candidates = asyncio.run(service.scan())

    assert len(candidates) == 1
    assert candidates[0].device_id == "dev_minix"
    assert candidates[0].support_level == "detected_unverified"
    assert candidates[0].candidate_profile_ids == ["seznik-minix-s1-lyin48d-gy"]
    assert candidates[0].printable is False
    assert candidates[0].next_required_stage == "read_only_verification"
    assert candidates[0].reason == "Service UUID and name match; model query required."


def test_scan_does_not_claim_generic_ff00_printers_are_supported() -> None:
    service = PrinterDiscoveryService(
        profiles=load_profiles(),
        adapter=MockBleAdapter(
            advertisements=[
                BleAdvertisement(
                    device_id="dev_generic",
                    name="Generic FF00 Printer",
                    service_uuids=[FF00],
                    rssi=-62,
                )
            ],
        ),
    )

    candidates = asyncio.run(service.scan())

    assert candidates[0].support_level == "detected_unverified"
    assert candidates[0].printable is False
    assert candidates[0].reason == "Service UUID matches; model query required."


def test_read_only_verification_matches_model_and_firmware_without_enabling_print() -> None:
    service = PrinterDiscoveryService(
        profiles=load_profiles(),
        adapter=MockBleAdapter(
            advertisements=[
                BleAdvertisement(
                    device_id="dev_minix",
                    name="Seznik MiniX_0194_LE",
                    service_uuids=[FF00],
                    rssi=-48,
                )
            ],
            read_only_infos={
                "dev_minix": ReadOnlyDeviceInfo(
                    model_response="S1_LYiN48D_GY",
                    firmware="V1.9.11",
                    services=[FF00],
                    write_characteristics=["0000ff02-0000-1000-8000-00805f9b34fb"],
                    notify_characteristics=[
                        "0000ff01-0000-1000-8000-00805f9b34fb",
                        "0000ff03-0000-1000-8000-00805f9b34fb",
                    ],
                    raw_notifications=[],
                )
            },
        ),
    )

    verification = asyncio.run(service.read_only_verify("dev_minix"))

    assert verification.status == "read_only_verified"
    assert verification.profile_id == "seznik-minix-s1-lyin48d-gy"
    assert verification.profile_support_level == "official"
    assert verification.model_response == "S1_LYiN48D_GY"
    assert verification.firmware == "V1.9.11"
    assert verification.printable is False
    assert verification.next_required_stage == "protocol_sanity_test"
    assert verification.reason == "Model and firmware match profile; protocol sanity test required."
