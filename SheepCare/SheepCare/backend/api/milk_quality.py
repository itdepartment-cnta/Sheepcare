"""
Milk Quality API - Upload, parsing, and batch SCC (milk quality) prediction.
"""

import os
import time
import uuid
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from ..data_access.db_manager import DatabaseManager
from ..core.spectral_parser import SpectralParser, ID_COLUMN
from ..core.spectral_model import MilkQualityLoader
from ..utils.helpers import get_data_dir, append_result_column

router = APIRouter()
db = DatabaseManager()
loader = MilkQualityLoader()

RESULT_COLORS = {
    "Lower": ("2E7D32", "E8F5E9"),
    "Upper": ("C0503A", "FDE8E8"),
}


class SampleResultResponse(BaseModel):
    animal_id: str
    result: str


class MilkQualityUploadResponse(BaseModel):
    upload_id: int
    farm_id: int
    filename: str
    result_file: str = ""
    total_samples: int
    lower_count: int
    upper_count: int
    results: List[SampleResultResponse]
    upload_date: Optional[str] = None
    processed_at: Optional[str] = None
    processing_time_ms: float = 0


class MilkQualityUploadSummaryResponse(BaseModel):
    id: int
    farm_id: int
    farm_name: str
    filename: str
    upload_date: str
    processed_at: Optional[str]
    total_samples: int
    lower_count: int
    upper_count: int


class MilkQualityUploadDetailResponse(MilkQualityUploadSummaryResponse):
    results: List[dict]


class MilkQualityResultResponse(BaseModel):
    id: int
    animal_id: int
    upload_id: int
    result: str
    created_at: str
    animal_tag: str
    animal_name: str
    filename: str
    upload_date: str
    farm_name: str


@router.post("/uploads/", response_model=MilkQualityUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    farm_id: int = Form(...),
):
    """
    Upload a spectral Excel file for a specific farm and run milk quality
    (SCC) prediction on each row.
    """
    started_at = time.perf_counter()

    farm = db.get_farm(farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only .xlsx and .xls are supported.",
        )

    data_dir = get_data_dir()
    uploads_dir = os.path.join(data_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    safe_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(uploads_dir, safe_filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        df = SpectralParser.parse_content(content, file.filename)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {str(e)}")

    if df.empty:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=422, detail="No valid sample rows found in file.")

    upload_id = db.create_milk_quality_upload(farm_id, file.filename)

    features = SpectralParser.extract_features(df)
    try:
        predictions = loader.predict(features)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    results = []
    lower_count = 0
    upper_count = 0

    for sample_id_raw, result_label in zip(df[ID_COLUMN], predictions):
        sample_id = str(sample_id_raw).strip()
        db_animal_id = db.add_animal(farm_id, sample_id, name=sample_id)
        db.save_milk_quality_result(db_animal_id, upload_id, result_label)

        if result_label == "Lower":
            lower_count += 1
        elif result_label == "Upper":
            upper_count += 1

        results.append(SampleResultResponse(animal_id=sample_id, result=result_label))

    db.finalize_milk_quality_upload(upload_id, len(results), lower_count, upper_count)
    upload_record = db.get_milk_quality_upload(upload_id)

    result_file_name = ""
    try:
        result_filename = f"{uuid.uuid4().hex}_resultado_{file.filename}"
        result_path = os.path.join(uploads_dir, result_filename)
        append_result_column(
            file_path,
            result_path,
            id_to_result={r.animal_id: r.result for r in results},
            result_colors=RESULT_COLORS,
        )
        result_file_name = result_filename
    except Exception:
        pass  # Non-critical: continue even if Excel generation fails

    if os.path.exists(file_path):
        os.remove(file_path)

    return MilkQualityUploadResponse(
        upload_id=upload_id,
        farm_id=farm_id,
        filename=file.filename,
        result_file=result_file_name,
        total_samples=len(results),
        lower_count=lower_count,
        upper_count=upper_count,
        results=results,
        upload_date=upload_record["upload_date"] if upload_record else None,
        processed_at=upload_record["processed_at"] if upload_record else None,
        processing_time_ms=(time.perf_counter() - started_at) * 1000,
    )


@router.get("/uploads/", response_model=List[MilkQualityUploadSummaryResponse])
async def list_uploads(farm_id: Optional[int] = None):
    """List all milk quality uploads, optionally filtered by farm."""
    uploads = db.list_milk_quality_uploads(farm_id)
    return [MilkQualityUploadSummaryResponse(**u) for u in uploads]


@router.get("/uploads/{upload_id}", response_model=MilkQualityUploadDetailResponse)
async def get_upload(upload_id: int):
    """Get upload details with milk quality results."""
    upload = db.get_milk_quality_upload(upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    results = db.get_milk_quality_results(upload_id=upload_id)
    return MilkQualityUploadDetailResponse(
        **upload,
        results=[dict(r) for r in results],
    )


@router.get("/results/", response_model=List[MilkQualityResultResponse])
async def list_results(
    farm_id: Optional[int] = Query(None),
    upload_id: Optional[int] = Query(None),
):
    """List milk quality results with optional filters."""
    results = db.get_milk_quality_results(farm_id=farm_id, upload_id=upload_id)
    return [MilkQualityResultResponse(**r) for r in results]


@router.get("/uploads/download/{filename}")
async def download_result(filename: str):
    """Download a generated result file."""
    data_dir = get_data_dir()
    uploads_dir = os.path.join(data_dir, "uploads")
    file_path = os.path.join(uploads_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)
