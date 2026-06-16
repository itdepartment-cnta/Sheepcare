"""
DetectionJob - Wrapper for running batch estrus detection.
Can be used both synchronously (during upload) and as a joblib task.
"""

import joblib
from typing import List, Dict, Any, Optional
from .engine import ProcessingEngine
from .excel_parser import ExcelParser


def process_animal_readings(
    values: List[float],
    engine: Optional[ProcessingEngine] = None,
) -> Dict[str, Any]:
    """
    Run estrus detection on a list of reading values.

    Args:
        values: List of numerical resistance values (one per date)
        engine: Optional ProcessingEngine instance (creates default if None)

    Returns:
        Dict with estrus_detected, confidence, probability
    """
    if engine is None:
        engine = ProcessingEngine()

    processed = engine.process_signal(values)
    result = engine.predict_estrus(processed)
    return result


def batch_process(
    animals_data: List[Dict[str, Any]],
    model_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Process multiple animals in batch.

    Args:
        animals_data: List from ExcelParser.parse()
            [{'animal_id': str, 'readings': [{'date': str, 'value': float}, ...]}, ...]
        model_path: Optional path to ML model file

    Returns:
        List of dicts with animal_id, result, confidence, probability
    """
    engine = ProcessingEngine(model_path)
    results = []

    for animal in animals_data:
        values = [r["value"] for r in animal["readings"]]
        detection = process_animal_readings(values, engine)

        results.append(
            {
                "animal_id": animal["animal_id"],
                "estrus_detected": detection["estrus_detected"],
                "result": "Celo" if detection["estrus_detected"] else "No celo",
                "confidence": detection["confidence"],
                "probability": detection["probability"],
            }
        )

    return results


# Joblib-compatible wrapper for parallel processing
def process_single_animal(animal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single animal. Compatible with joblib.Parallel.
    """
    values = [r["value"] for r in animal_data["readings"]]
    detection = process_animal_readings(values)
    return {
        "animal_id": animal_data["animal_id"],
        "estrus_detected": detection["estrus_detected"],
        "result": "Celo" if detection["estrus_detected"] else "No celo",
        "confidence": detection["confidence"],
        "probability": detection["probability"],
    }


def batch_process_parallel(
    animals_data: List[Dict[str, Any]],
    n_jobs: int = -1,
) -> List[Dict[str, Any]]:
    """
    Process multiple animals in parallel using joblib.

    Args:
        animals_data: List from ExcelParser.parse()
        n_jobs: Number of parallel jobs (-1 = use all CPUs)

    Returns:
        List of dicts with animal_id, result, confidence, probability
    """
    return joblib.Parallel(n_jobs=n_jobs)(
        joblib.delayed(process_single_animal)(animal) for animal in animals_data
    )
