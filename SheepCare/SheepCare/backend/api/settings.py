"""
Settings API - System configuration, sync control, and cloud credentials.
"""

import os
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from ..data_access.db_manager import DatabaseManager
from ..data_access.sync_manager import SyncService
from ..utils.helpers import get_project_root

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
