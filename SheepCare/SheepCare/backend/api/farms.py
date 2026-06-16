"""
Farms API - CRUD operations for farms.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from ..data_access.db_manager import DatabaseManager
from ..data_access.farmcalendar_client import FarmCalendarClient

router = APIRouter()
db = DatabaseManager()


class FarmCreate(BaseModel):
    name: str
    location: str = ""


class FarmUpdate(BaseModel):
    name: str
    location: str = ""


class FarmResponse(BaseModel):
    id: int
    name: str
    location: str
    created_at: str


def _sync_farm_to_calendar(farm_id: int, name: str, location: str) -> None:
    try:
        calendar = FarmCalendarClient()
        fc_uuid = calendar.sync_farm(name, location)
        if fc_uuid:
            db.save_fc_uuid("farm", farm_id, fc_uuid)
            parcel_uuid = calendar.sync_parcel(fc_uuid, f"parcel_{farm_id}")
            if parcel_uuid:
                db.save_fc_uuid("parcel", farm_id, parcel_uuid)
    except Exception:
        pass


@router.post("/", response_model=FarmResponse, status_code=201)
async def create_farm(farm: FarmCreate, background_tasks: BackgroundTasks):
    """Register a new farm."""
    farm_id = db.add_farm(farm.name, farm.location)
    result = db.get_farm(farm_id)
    background_tasks.add_task(_sync_farm_to_calendar, farm_id, farm.name, farm.location)
    return FarmResponse(**result)


@router.get("/", response_model=List[FarmResponse])
async def list_farms():
    """List all registered farms."""
    farms = db.list_farms()
    return [FarmResponse(**f) for f in farms]


@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(farm_id: int):
    """Get farm details by ID."""
    farm = db.get_farm(farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return FarmResponse(**farm)


@router.put("/{farm_id}", response_model=FarmResponse)
async def update_farm(farm_id: int, farm: FarmUpdate):
    """Update farm details."""
    success = db.update_farm(farm_id, farm.name, farm.location)
    if not success:
        raise HTTPException(status_code=404, detail="Farm not found")
    result = db.get_farm(farm_id)

    # Sync name change to FC
    try:
        calendar = FarmCalendarClient()
        calendar.sync_farm(farm.name, farm.location)
    except Exception:
        pass

    return FarmResponse(**result)


@router.delete("/{farm_id}", status_code=204)
async def delete_farm(farm_id: int):
    """Delete a farm and all associated data (cascade)."""
    farm = db.get_farm(farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    db.delete_farm(farm_id)
