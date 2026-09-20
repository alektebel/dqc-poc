"""FastAPI entry point — DQC generator API.

Run with:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

# Ensure project root is on sys.path so ``import src...`` works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

app = FastAPI(
    title="RegLLM — DQC Generator",
    description="Data Quality Check generator for banking regulatory compliance (COREP/FINREP).",
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:4200").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router set is configurable so the slim AWS/DQC deployment can ship only
# what it needs (REGLLM_ROUTERS=dqc). This standalone DQC PoC ships the DQC
# generator surface only. Routers that fail to import (e.g. an optional
# heavy dependency missing) are skipped with a warning instead of taking
# the whole API down.
_ALL_ROUTERS = ("dqc", "revisions")
_enabled = [r.strip() for r in os.getenv("REGLLM_ROUTERS", "dqc,revisions").split(",") if r.strip()]
if "all" in _enabled:
    _enabled = list(_ALL_ROUTERS)

for _name in _enabled:
    try:
        _module = __import__(f"api.routers.{_name}", fromlist=["router"])
        app.include_router(_module.router)
    except Exception:  # pragma: no cover — depends on installed extras
        logging.getLogger(__name__).warning(
            "Router %r could not be mounted — skipping", _name, exc_info=True
        )


# The four screens are served by this same app, so the browser talks to one
# origin: no CORS, no second container, no proxy config to keep in sync.
_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if _WEB_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=_WEB_DIR, html=True), name="app")

    @app.get("/", include_in_schema=False)
    def _home() -> RedirectResponse:
        return RedirectResponse("/app/home.html")


@app.get("/health")
def health() -> dict:
    from src.knowledge import get_client
    backend = get_client().detect_backend()
    return {"status": "ok", "llm_backend": backend}
