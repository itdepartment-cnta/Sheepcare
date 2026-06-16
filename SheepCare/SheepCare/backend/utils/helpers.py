"""
Utility helpers for SHEEPCARE backend.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional


def get_project_root() -> str:
    """Return the absolute path to the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir() -> str:
    """Return the path to the data directory, creating it if needed."""
    db_path = os.environ.get("SHEEPCARE_DB_PATH")
    if db_path:
        data_dir = os.path.dirname(db_path)
    else:
        data_dir = os.path.join(get_project_root(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to a resource, works for dev and for PyInstaller.
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = get_project_root()
    return os.path.join(base_path, relative_path)


def format_timestamp(dt_str: str, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format an ISO datetime string for display."""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime(fmt)
    except (ValueError, TypeError):
        return dt_str


def format_confidence(confidence: float) -> str:
    """Format confidence score as percentage string."""
    return f"{confidence * 100:.1f}%"


def date_range_filter(
    readings: List[dict],
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[dict]:
    """
    Filter readings list by date range.
    If `days` is provided, filter to last N days.
    """
    if not readings:
        return []

    if days is not None:
        cutoff = datetime.now() - timedelta(days=days)
        return [
            r
            for r in readings
            if datetime.fromisoformat(r.get("timestamp", "")).replace(tzinfo=None)
            >= cutoff
        ]

    if start_date:
        start = datetime.fromisoformat(start_date)
        readings = [
            r
            for r in readings
            if datetime.fromisoformat(r.get("timestamp", "")).replace(tzinfo=None)
            >= start
        ]

    if end_date:
        end = datetime.fromisoformat(end_date)
        readings = [
            r
            for r in readings
            if datetime.fromisoformat(r.get("timestamp", "")).replace(tzinfo=None)
            <= end
        ]

    return readings
