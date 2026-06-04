import json
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from minixd.app import create_app


def test_hardware_test_export_runs_read_only_verification_without_print_commands() -> None:
    client = TestClient(create_app(mock=True))

    response = client.post(
        "/v1/diagnostics/hardware-test",
        json={"deviceId": "mock-minix-0194", "stage": "read_only_verification"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert {
            "device.json",
            "profile.json",
            "ble-discovery.json",
            "model-response.bin",
            "firmware-response.bin",
            "notifications.log",
            "commands.log",
            "print-transfer-manifest.json",
            "band-manifest.json",
            "finalizer-result.json",
            "safety-report.json",
            "user-confirmation.json",
            "app-version.json",
            "README.md",
        } <= names

        device = json.loads(archive.read("device.json"))
        assert device["deviceId"] == "mock-minix-0194"
        assert device["status"] == "read_only_verified"
        assert device["printable"] is False
        assert device["nextRequiredStage"] == "protocol_sanity_test"

        profile = json.loads(archive.read("profile.json"))
        assert profile["id"] == "seznik-minix-s1-lyin48d-gy"
        assert profile["supportLevel"] == "official"

        transfer_manifest = json.loads(archive.read("print-transfer-manifest.json"))
        assert transfer_manifest["stage"] == "read_only_verification"
        assert transfer_manifest["printCommandsSent"] is False
        assert transfer_manifest["rasterBytesIncluded"] is False

        safety_report = json.loads(archive.read("safety-report.json"))
        assert safety_report["printingLocked"] is True
        assert safety_report["certificationComplete"] is False

        assert archive.read("model-response.bin") == b"S1_LYiN48D_GY"
        assert archive.read("firmware-response.bin") == b"V1.9.11"
        assert "approvalToken" not in response.content.decode("latin-1")


def test_hardware_test_export_reports_missing_device() -> None:
    client = TestClient(create_app(mock=True))

    response = client.post(
        "/v1/diagnostics/hardware-test",
        json={"deviceId": "missing-printer", "stage": "read_only_verification"},
    )

    assert response.status_code == 404
