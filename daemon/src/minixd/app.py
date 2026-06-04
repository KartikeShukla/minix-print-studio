from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from minixd import __version__

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
        return {"profiles": load_profiles()}

    return app
