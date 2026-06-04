from fastapi.testclient import TestClient

from minixd.app import create_app


def test_printer_scan_endpoint_returns_mock_candidates_without_print_permission() -> None:
    client = TestClient(create_app(mock=True))

    response = client.get("/v1/printers/scan")

    assert response.status_code == 200
    body = response.json()
    assert body["printers"] == [
        {
            "deviceId": "mock-minix-0194",
            "name": "Seznik MiniX_0194_LE",
            "serviceUuids": ["0000ff00-0000-1000-8000-00805f9b34fb"],
            "rssi": -42,
            "supportLevel": "detected_unverified",
            "candidateProfileIds": ["seznik-minix-s1-lyin48d-gy"],
            "printable": False,
            "nextRequiredStage": "read_only_verification",
            "reason": "Service UUID and name match; model query required.",
        }
    ]


def test_printer_scan_endpoint_supports_documented_post_method() -> None:
    client = TestClient(create_app(mock=True))

    response = client.post("/v1/printers/scan")

    assert response.status_code == 200
    assert response.json()["printers"][0]["deviceId"] == "mock-minix-0194"


def test_read_only_verify_endpoint_keeps_matching_mock_printer_untrusted() -> None:
    client = TestClient(create_app(mock=True))

    response = client.post(
        "/v1/printers/read-only-verify",
        json={"deviceId": "mock-minix-0194"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "read_only_verified"
    assert body["deviceId"] == "mock-minix-0194"
    assert body["profileId"] == "seznik-minix-s1-lyin48d-gy"
    assert body["profileSupportLevel"] == "official"
    assert body["modelResponse"] == "S1_LYiN48D_GY"
    assert body["firmware"] == "V1.9.11"
    assert body["printable"] is False
    assert body["nextRequiredStage"] == "protocol_sanity_test"
