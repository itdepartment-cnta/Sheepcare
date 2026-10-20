"""
Farms API - CRUD operations for farms.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from ..data_access.db_manager import DatabaseManager
from ..data_access.farmcalendar_client import FarmCalendarClient

router = APIRouter()
db = DatabaseManager()


class _Coordinates(BaseModel):
    # Real position of the farm (used by the weather service). Both or none.
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _both_or_none(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class FarmCreate(_Coordinates):
    name: str
    location: str = ""


class FarmUpdate(_Coordinates):
    name: str
    location: str = ""


class FarmResponse(BaseModel):
    id: int
    name: str
    location: str
    created_at: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Relación de la persona con la granja según la nube: "owner", "shared" o "admin".
    # None en una granja solo local (la persona es quien la creó).
    access: Optional[str] = None


def _respuesta(farm: dict) -> "FarmResponse":
    return FarmResponse(**{**farm, "access": farm.get("cloud_access")})


def _exigir_gestion(farm: dict) -> None:
    """Una granja compartida se ve y se le suben datos, pero no se edita ni se borra.

    La nube lo comprueba igualmente, pero aquí hay que decirlo antes: si no, el cambio
    local no se enviaría nunca y el equipo mostraría algo que la nube no tiene.
    """
    if farm.get("cloud_access") == "shared":
        raise HTTPException(
            status_code=403,
            detail="Esta granja está compartida contigo: solo quien la posee puede editarla o borrarla.",
        )


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
    farm_id = db.add_farm(farm.name, farm.location, farm.latitude, farm.longitude)
    result = db.get_farm(farm_id)
    background_tasks.add_task(_sync_farm_to_calendar, farm_id, farm.name, farm.location)
    return _respuesta(result)


@router.get("/", response_model=List[FarmResponse])
async def list_farms():
    """List all registered farms."""
    farms = db.list_farms()
    return [_respuesta(f) for f in farms]


@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(farm_id: int):
    """Get farm details by ID."""
    farm = db.get_farm(farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return _respuesta(farm)


@router.put("/{farm_id}", response_model=FarmResponse)
async def update_farm(farm_id: int, farm: FarmUpdate):
    """Update farm details."""
    actual = db.get_farm(farm_id)
    if not actual:
        raise HTTPException(status_code=404, detail="Farm not found")
    _exigir_gestion(actual)
    # Coordinates omitted -> untouched; sent (even as null) -> replaced.
    coords = None
    if {"latitude", "longitude"} & farm.model_fields_set:
        coords = (farm.latitude, farm.longitude)
    success = db.update_farm(farm_id, farm.name, farm.location, coords)
    if not success:
        raise HTTPException(status_code=404, detail="Farm not found")
    result = db.get_farm(farm_id)

    # Sync name change to FC
    try:
        calendar = FarmCalendarClient()
        calendar.sync_farm(farm.name, farm.location)
    except Exception:
        pass

    return _respuesta(result)


@router.delete("/{farm_id}", status_code=204)
async def delete_farm(farm_id: int):
    """Delete a farm and all associated data (cascade)."""
    farm = db.get_farm(farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    _exigir_gestion(farm)
    db.delete_farm(farm_id)
