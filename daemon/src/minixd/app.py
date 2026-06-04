from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from minixd import __version__
from minixd.api.jobs import create_jobs_router
from minixd.api.render import create_render_router
from minixd.render.preview_store import PreviewStore

PROFILE_REGISTRY_VERSION = "2026.06.04"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = PROJECT_ROOT / "profiles" / "seznik-minix-s1-lyin48d-gy" / "profile.json"


def load_profiles() -> list[dict[str, Any]]:
    return [json.loads(PROFILE_PATH.read_text(encoding="utf-8"))]


def create_app(*, mock: bool = False) -> FastAPI:
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
    app.include_router(create_render_router(preview_store=preview_store))
    app.include_router(create_jobs_router(profiles=profiles_data, preview_store=preview_store))

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
