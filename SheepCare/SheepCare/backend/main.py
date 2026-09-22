"""
SHEEPCARE Backend - FastAPI Application Entry Point.
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .api import farms, uploads, results, animals, settings, milk_quality

logger = logging.getLogger(__name__)

_AUTO_SYNC_INTERVAL = int(os.environ.get("AUTO_SYNC_INTERVAL_MINUTES", "15")) * 60


def _run_auto_sync() -> None:
    """Blocking: check connectivity and run bidirectional sync if reachable."""
    from .data_access.sync_manager import SyncService
    svc = SyncService()
    if not svc.is_configured:
        return
    if not svc.check_cloud_connectivity():
        return
    push = svc.sync_to_cloud()
    if push.get("success"):
        svc.pull_from_cloud()
    logger.info("Auto-sync completed: %s", push)


async def _auto_sync_loop() -> None:
    await asyncio.sleep(30)  # let the app finish starting up
    while True:
        try:
            await asyncio.to_thread(_run_auto_sync)
        except Exception:
            logger.exception("Auto-sync task error")
        await asyncio.sleep(_AUTO_SYNC_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_auto_sync_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="SHEEPCARE API",
    description="Smart Estrus Detection System - Backend API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend dev server and production
origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:8002",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(farms.router, prefix="/api/farms", tags=["Farms"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])
app.include_router(animals.router, prefix="/api/animals", tags=["Animals"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(milk_quality.router, prefix="/api/milk-quality", tags=["Milk Quality"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Servir frontend React ─────────────────────────────────────────────────────
# En modo PyInstaller, los archivos están junto al ejecutable.
# En desarrollo, están en frontend/dist/ relativo a la raíz del proyecto.
def _frontend_dist() -> str:
    if getattr(sys, "frozen", False):
        # En bundle PyInstaller, los data files están en sys._MEIPASS (_internal/)
        # no junto al ejecutable
        return os.path.join(sys._MEIPASS, "frontend", "dist")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "frontend", "dist")


_DIST = _frontend_dist()

if os.path.isdir(_DIST):
    _assets = os.path.join(_DIST, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        return FileResponse(os.path.join(_DIST, "favicon.svg"))

    @app.get("/icons.svg", include_in_schema=False)
    async def icons():
        return FileResponse(os.path.join(_DIST, "icons.svg"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = os.path.join(_DIST, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
