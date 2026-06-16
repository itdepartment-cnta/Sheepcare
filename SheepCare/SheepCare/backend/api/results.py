"""
Results API - Query detection results with filters.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional
from ..data_access.db_manager import DatabaseManager

router = APIRouter()
db = DatabaseManager()


class ResultResponse(BaseModel):
    id: int
    animal_id: int
    upload_id: int
    result: str
    confidence: float
    probability: float
    created_at: str
    animal_tag: str
    animal_name: str
    filename: str
    upload_date: str
    farm_name: str


class LatestResultResponse(BaseModel):
    id: int
    animal_id: int
    upload_id: int
    result: str
    confidence: float
    probability: float
    animal_tag: str
    animal_name: str
    filename: str
    upload_date: str
    farm_name: str


@router.get("/", response_model=List[ResultResponse])
async def list_results(
    farm_id: Optional[int] = Query(None),
    upload_id: Optional[int] = Query(None),
    result: Optional[str] = Query(None),
):
    """List detection results with optional filters."""
    results = db.get_results(farm_id=farm_id, upload_id=upload_id, result_filter=result)
    return [ResultResponse(**r) for r in results]


@router.get("/latest", response_model=Optional[LatestResultResponse])
async def get_latest_result(farm_id: Optional[int] = Query(None)):
    """Get the most recent detection result."""
    result = db.get_latest_result(farm_id)
    if result:
        return LatestResultResponse(**result)
    return None
