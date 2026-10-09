"""
Settings API - System configuration, sync control, and cloud credentials.
"""

import logging
import os
import time
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from ..data_access.db_manager import DatabaseManager
from ..data_access.sync_manager import SyncService
from ..utils.helpers import get_project_root

logger = logging.getLogger(__name__)
router = APIRouter()
db = DatabaseManager()


class SystemInfoResponse(BaseModel):
    db_path: str
    project_root: str
    models_path: str
    farmcalendar_url: str


class SyncStatusResponse(BaseModel):
    last_sync: Optional[str]
    last_status: Optional[str]
    last_error: Optional[str]


class SyncResponse(BaseModel):
    success: bool
    synced_count: int
    error: Optional[str] = None


class CloudConfigResponse(BaseModel):
    configured: bool
    email: str = ""
    cloud_url: str = ""
    client_id: int = 0


class CloudConfigRequest(BaseModel):
    cloud_url: str
    email: str
    password: str


WEATHER_API_KEY_SETTING = "weather_openweathermap_api_key"


class WeatherConfigResponse(BaseModel):
    configured: bool
    # Last four characters only, so the user can recognise which key is saved.
    key_hint: str = ""


class WeatherConfigRequest(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("api_key must not be empty")
        if any(c.isspace() for c in v):
            raise ValueError("api_key must not contain spaces")
        return v


class ConnectivityResponse(BaseModel):
    reachable: bool
    cloud_url: str
    checked_at: str


@router.get("/system", response_model=SystemInfoResponse)
async def get_system_info():
    """Get system paths and configuration."""
    project_root = get_project_root()
    fc_url = os.environ.get(
        "FARMCALENDAR_API_URL",
        "http://localhost:8002/api/v1/",
    )
    return SystemInfoResponse(
        db_path=db.db_path,
        project_root=project_root,
        models_path=f"{project_root}/models",
        farmcalendar_url=fc_url,
    )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status():
    """Get last sync status."""
    last = db.get_last_sync()
    if last:
        return SyncStatusResponse(
            last_sync=last["last_sync_at"],
            last_status=last["status"],
            last_error=last.get("last_error", ""),
        )
    return SyncStatusResponse(last_sync=None, last_status=None, last_error=None)


@router.get("/sync/connectivity", response_model=ConnectivityResponse)
async def check_cloud_connectivity():
    """Check if the configured cloud URL is currently reachable."""
    sync_service = SyncService(db)
    reachable = sync_service.is_configured and sync_service.check_cloud_connectivity()
    return ConnectivityResponse(
        reachable=reachable,
        cloud_url=sync_service.cloud_url,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/sync/now", response_model=SyncResponse)
async def sync_now():
    """Force a full bidirectional sync (push + pull) with the cloud."""
    sync_service = SyncService(db)
    try:
        # Push local data to cloud
        push_result = sync_service.sync_to_cloud()
        # Pull cloud data to local
        if push_result.get("success"):
            sync_service.pull_from_cloud()

        total = push_result.get("synced_count", 0)
        return SyncResponse(
            success=push_result.get("success", False),
            synced_count=total,
            error=push_result.get("error"),
        )
    except Exception as e:
        return SyncResponse(success=False, synced_count=0, error=str(e))


@router.get("/cloud/config", response_model=CloudConfigResponse)
async def get_cloud_config():
    """Get current cloud sync configuration."""
    config = db.get_cloud_config()
    if config and config.get("email"):
        return CloudConfigResponse(
            configured=True,
            email=config["email"],
            cloud_url=config.get("cloud_url", ""),
            client_id=config.get("client_id", 0),
        )
    return CloudConfigResponse(configured=False)


@router.post("/cloud/config", response_model=CloudConfigResponse)
async def save_cloud_config(req: CloudConfigRequest, background_tasks: BackgroundTasks):
    """Save cloud credentials and test the connection."""
    sync_service = SyncService(db)
    sync_service.configure(req.cloud_url, req.email, req.password)

    # Test login
    token = sync_service._ensure_token()
    if not token:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail="Failed to authenticate with cloud. Check credentials.",
        )

    # Trigger immediate sync in background now that credentials are confirmed
    from ..main import _run_auto_sync
    background_tasks.add_task(_run_auto_sync)

    return CloudConfigResponse(
        configured=True,
        email=req.email,
        cloud_url=req.cloud_url,
        client_id=sync_service.client_id,
    )


@router.delete("/cloud/config", response_model=dict)
async def clear_cloud_config():
    """Remove cloud credentials."""
    sync_service = SyncService(db)
    sync_service.clear_config()
    return {"success": True, "message": "Cloud configuration removed"}


def write_weather_key_file(key: str) -> None:
    """Deja la clave donde Weather la relee en cada uso (el launcher fija la ruta
    en OPENWEATHERMAP_KEY_FILE). Una clave vacia borra el fichero. Sin ruta
    configurada (desarrollo, Docker) no hace nada."""
    path = os.environ.get("OPENWEATHERMAP_KEY_FILE", "")
    if not path:
        return
    ultimo = None
    for _ in range(5):
        # Weather puede estar leyendo el fichero justo ahora (Windows lo bloquea)
        try:
            if key:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(key)
                os.replace(tmp, path)
            elif os.path.exists(path):
                os.remove(path)
            return
        except OSError as e:
            ultimo = e
            time.sleep(0.1)
    raise ultimo


def sync_weather_key_file() -> None:
    """Al arrancar: vuelve a dejar en disco la clave guardada (p. ej. tras reinstalar)."""
    try:
        write_weather_key_file(db.get_setting(WEATHER_API_KEY_SETTING))
    except OSError:
        logger.warning("No se pudo escribir la clave de OpenWeatherMap", exc_info=True)


def _weather_config() -> WeatherConfigResponse:
    key = db.get_setting(WEATHER_API_KEY_SETTING)
    if not key:
        return WeatherConfigResponse(configured=False)
    return WeatherConfigResponse(configured=True, key_hint=key[-4:])


@router.get("/weather", response_model=WeatherConfigResponse)
async def get_weather_config():
    """Whether the user has saved an OpenWeatherMap API key (never returns it)."""
    return _weather_config()


@router.put("/weather", response_model=WeatherConfigResponse)
async def save_weather_config(req: WeatherConfigRequest):
    """Save the user's OpenWeatherMap API key."""
    try:
        write_weather_key_file(req.api_key)
    except OSError:
        logger.exception("No se pudo escribir la clave de OpenWeatherMap")
        raise HTTPException(500, "No se pudo guardar la clave en este equipo. Inténtalo de nuevo.")
    db.set_setting(WEATHER_API_KEY_SETTING, req.api_key)
    return _weather_config()


@router.delete("/weather", response_model=WeatherConfigResponse)
async def clear_weather_config():
    """Remove the saved OpenWeatherMap API key."""
    try:
        write_weather_key_file("")
    except OSError:
        logger.exception("No se pudo borrar la clave de OpenWeatherMap")
        raise HTTPException(500, "No se pudo eliminar la clave en este equipo. Inténtalo de nuevo.")
    db.delete_setting(WEATHER_API_KEY_SETTING)
    return _weather_config()
