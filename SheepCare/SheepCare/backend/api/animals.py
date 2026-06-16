"""
Animals API - CRUD and history for animals.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from ..data_access.db_manager import DatabaseManager

router = APIRouter()
db = DatabaseManager()


class AnimalCreate(BaseModel):
    farm_id: int
    external_tag: str
    name: str = ""


class AnimalUpdate(BaseModel):
    name: str


class AnimalResponse(BaseModel):
    id: int
    farm_id: int
    external_tag: str
    name: str
    created_at: str


class AnimalReadingResponse(BaseModel):
    id: int
    reading_date: str
    value: float
    source_file: str


class AnimalResultResponse(BaseModel):
    id: int
    upload_id: int
    result: str
    confidence: float
    probability: float
    created_at: str
    filename: str
    upload_date: str
    farm_name: str


class AnimalDetailResponse(AnimalResponse):
    readings: List[AnimalReadingResponse] = []
    results: List[AnimalResultResponse] = []


@router.get("/", response_model=List[AnimalResponse])
async def list_animals(farm_id: Optional[int] = Query(None)):
    """List animals, optionally filtered by farm."""
    animals = db.list_animals(farm_id)
    return [AnimalResponse(**a) for a in animals]


@router.get("/{animal_id}", response_model=AnimalDetailResponse)
async def get_animal(animal_id: int):
    """Get animal details with readings and results."""
    animal = db.get_animal(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")

    readings = db.get_animal_readings(animal_id)
    results = db.get_animal_results(animal_id)

    return AnimalDetailResponse(
        **animal,
        readings=[AnimalReadingResponse(**r) for r in readings],
        results=[AnimalResultResponse(**r) for r in results],
    )


@router.get("/{animal_id}/history", response_model=List[AnimalResultResponse])
async def get_animal_history(animal_id: int):
    """Get detection history for a specific animal."""
    animal = db.get_animal(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")

    results = db.get_animal_results(animal_id)
    return [AnimalResultResponse(**r) for r in results]


@router.post("/", response_model=AnimalResponse, status_code=201)
async def create_animal(animal: AnimalCreate):
    """Register a new animal under a farm."""
    farm = db.get_farm(animal.farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    animal_id = db.add_animal(animal.farm_id, animal.external_tag, animal.name)
    result = db.get_animal(animal_id)
    return AnimalResponse(**result)


@router.put("/{animal_id}", response_model=AnimalResponse)
async def update_animal(animal_id: int, animal: AnimalUpdate):
    """Update animal name."""
    success = db.update_animal(animal_id, animal.name)
    if not success:
        raise HTTPException(status_code=404, detail="Animal not found")
    result = db.get_animal(animal_id)
    return AnimalResponse(**result)


@router.delete("/{animal_id}", status_code=204)
async def delete_animal(animal_id: int):
    """Delete an animal and all its readings/results."""
    animal = db.get_animal(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")
    db.delete_animal(animal_id)
