from fastapi.testclient import TestClient

from minixd.app import create_app


def test_health_endpoint_exposes_registry_and_mock_mode() -> None:
    client = TestClient(create_app(mock=True))

    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "version": "0.1.0",
        "profileRegistryVersion": "2026.06.04",
        "mock": True,
    }


def test_profile_endpoint_returns_official_seznik_profile() -> None:
    client = TestClient(create_app(mock=True))

    response = client.get("/v1/profiles")

    assert response.status_code == 200
    assert response.json()["profiles"][0]["id"] == "seznik-minix-s1-lyin48d-gy"
    assert response.json()["profiles"][0]["print"]["widthDots"] == 384


def test_local_renderer_origin_can_call_daemon_with_authorization_header() -> None:
    client = TestClient(create_app(mock=True))

    response = client.options(
        "/v1/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
