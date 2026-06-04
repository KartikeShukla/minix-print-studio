from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from minixd import __version__
from minixd.api.diagnostics import create_diagnostics_router
from minixd.api.jobs import create_jobs_router
from minixd.api.printers import create_printers_router
from minixd.api.render import create_render_router
from minixd.ble.bleak_adapter import BleakBleAdapter
from minixd.ble.discovery import (
    BleAdapter,
    BleAdvertisement,
    MockBleAdapter,
    PrinterDiscoveryService,
    ReadOnlyDeviceInfo,
)
from minixd.ble.profile_probe import ProfileReadOnlyProbe
from minixd.printing.queue import PrintQueue
from minixd.render.preview_store import PreviewStore

PROFILE_REGISTRY_VERSION = "2026.06.04"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = PROJECT_ROOT / "profiles" / "seznik-minix-s1-lyin48d-gy" / "profile.json"


def load_profiles() -> list[dict[str, Any]]:
    return [json.loads(PROFILE_PATH.read_text(encoding="utf-8"))]


def create_app(*, mock: bool = False, data_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="MiniX Print Studio daemon", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    profiles_data = load_profiles()
    preview_store = PreviewStore()
    print_queue = PrintQueue(
        profiles=profiles_data,
        preview_store=preview_store,
        mock=mock,
        job_store_path=(data_dir / "jobs.json") if data_dir is not None else None,
    )
    discovery_service = PrinterDiscoveryService(
        profiles=profiles_data,
        adapter=_create_ble_adapter(profiles=profiles_data, mock=mock),
    )
    app.include_router(create_render_router(preview_store=preview_store))
    app.include_router(create_printers_router(discovery_service=discovery_service))
    app.include_router(
        create_jobs_router(
            profiles=profiles_data,
            preview_store=preview_store,
            print_queue=print_queue,
        )
    )
    app.include_router(
        create_diagnostics_router(
            profiles=profiles_data,
            print_queue=print_queue,
            discovery_service=discovery_service,
            mock=mock,
            profile_registry_version=PROFILE_REGISTRY_VERSION,
        )
    )

    @app.get("/v1/health")
    def health() -> dict[str, bool | str]:
        return {
            "ok": True,
            "version": __version__,
            "profileRegistryVersion": PROFILE_REGISTRY_VERSION,
            "mock": mock,
        }

    @app.get("/v1/profiles")
    def profiles() -> dict[str, list[dict[str, Any]]]:
        return {"profiles": profiles_data}

    return app


def _create_ble_adapter(*, profiles: list[dict[str, Any]], mock: bool) -> BleAdapter:
    if not mock:
        return BleakBleAdapter(
            service_uuids=_profile_service_uuids(profiles),
            read_only_probe=ProfileReadOnlyProbe(profiles=profiles),
        )

    profile = profiles[0]
    ble = profile.get("ble")
    if not isinstance(ble, dict):
        return MockBleAdapter()

    service_uuid = ble.get("serviceUuid")
    write_char_uuid = ble.get("writeCharUuid")
    notify_char_uuids = ble.get("notifyCharUuids")
    if not isinstance(service_uuid, str) or not isinstance(write_char_uuid, str):
        return MockBleAdapter()
    if not isinstance(notify_char_uuids, list):
        return MockBleAdapter()

    device_id = "mock-minix-0194"
    return MockBleAdapter(
        advertisements=[
            BleAdvertisement(
                device_id=device_id,
                name="Seznik MiniX_0194_LE",
                service_uuids=[service_uuid],
                rssi=-42,
            )
        ],
        read_only_infos={
            device_id: ReadOnlyDeviceInfo(
                model_response="S1_LYiN48D_GY",
                firmware="V1.9.11",
                services=[service_uuid],
                write_characteristics=[write_char_uuid],
                notify_characteristics=[
                    notify_char_uuid
                    for notify_char_uuid in notify_char_uuids
                    if isinstance(notify_char_uuid, str)
                ],
                raw_notifications=[],
            )
        },
    )


def _profile_service_uuids(profiles: list[dict[str, Any]]) -> list[str]:
    service_uuids: list[str] = []
    for profile in profiles:
        ble = profile.get("ble")
        if not isinstance(ble, dict):
            continue
        service_uuid = ble.get("serviceUuid")
        if isinstance(service_uuid, str):
            service_uuids.append(service_uuid)
    return service_uuids
