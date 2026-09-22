"""
ProcessingEngine - Core AI processing pipeline.
Handles signal preprocessing, ML model inference, and estrus detection.
Reuses the same algorithm from the original SHEEPCARE MVP.
"""

import numpy as np
from typing import Optional, Dict, Any, List
from .models_loader import ModelsLoader


class ProcessingEngine:
    """
    Orchestrates the ML inference pipeline:
    1. Signal preprocessing / cleaning
    2. Feature extraction
    3. Model inference (estrus classification)
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._models_loader = ModelsLoader(model_path)
        self._latest_result: Optional[Dict[str, Any]] = None
        self._observers: List[callable] = []

    # ------------------------------------------------------------------
    # Observer pattern (for UI updates)
    # ------------------------------------------------------------------
    def attach(self, observer: callable) -> None:
        """Register an observer callback (called when a new result is ready)."""
        self._observers.append(observer)

    def detach(self, observer: callable) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def _notify_observers(self, result: Dict[str, Any]) -> None:
        for observer in self._observers:
            observer(result)

    # ------------------------------------------------------------------
    # Processing Pipeline
    # ------------------------------------------------------------------
    def process_signal(self, raw_data: List[float]) -> np.ndarray:
        """
        Clean and preprocess the raw sensor signal.

        Steps:
        - Convert to numpy array
        - Remove NaN / inf values
        - Apply low-pass filter (simple moving average)
        - Normalize to [0, 1] range
        """
        signal = np.array(raw_data, dtype=np.float64)

        # Remove invalid values
        signal = signal[np.isfinite(signal)]

        if len(signal) == 0:
            return np.array([])

        # Simple moving average filter (window size = 3)
        if len(signal) >= 3:
            kernel = np.ones(3) / 3
            signal = np.convolve(signal, kernel, mode="same")

        # Min-max normalization
        min_val, max_val = signal.min(), signal.max()
        if max_val > min_val:
            signal = (signal - min_val) / (max_val - min_val)
        else:
            signal = np.zeros_like(signal)

        return signal

    def _extract_features(self, processed_signal: np.ndarray) -> np.ndarray:
        """
        Extract statistical features from the processed signal.
        Returns a feature vector suitable for the ML model.
        """
        if len(processed_signal) == 0:
            return np.array([])

        features = [
            np.mean(processed_signal),
            np.std(processed_signal),
            np.median(processed_signal),
            np.max(processed_signal),
            np.min(processed_signal),
            np.percentile(processed_signal, 25),
            np.percentile(processed_signal, 75),
            np.ptp(processed_signal),  # peak-to-peak
            np.sum(np.abs(np.diff(processed_signal))),  # total variation
        ]
        return np.array(features)

    def predict_estrus(self, processed_data: np.ndarray) -> Dict[str, Any]:
        """
        Run the ML model to detect estrus.

        El modelo joblib (RandomForestClassifier) recibe directamente las
        lecturas procesadas (columnas B+ del Excel, fila 2+), no las
        features extraídas. Espera exactamente 2 lecturas por animal.

        Args:
            processed_data: Preprocessed signal array (readings values).

        Returns:
            Dict with keys:
                - 'estrus_detected': bool
                - 'confidence': float (0.0 - 1.0)
                - 'probability': float
                - 'features': list of extracted features
        """
        if len(processed_data) == 0:
            return {
                "estrus_detected": False,
                "confidence": 0.0,
                "probability": 0.0,
                "error": "Empty signal after preprocessing",
            }

        # Intentar inferencia con el modelo pasando las lecturas directamente
        probability = self._models_loader.predict(processed_data)

        if probability is None:
            # Fallback heurístico cuando no hay modelo cargado.
            # Normalizar primero porque la heurística espera valores en [0,1]
            norm_data = self._normalize_signal(processed_data)
            features = self._extract_features(norm_data)
            probability = self._heuristic_estrus_score(features)
        else:
            # Extraer features solo para el reporte (el modelo ya usó las lecturas)
            # Normalizar para que las features tengan sentido en el reporte
            norm_data = self._normalize_signal(processed_data)
            features = self._extract_features(norm_data)

        result = {
            "estrus_detected": probability >= 0.5,
            "confidence": max(probability, 1.0 - probability),
            "probability": float(probability),
            "features": features.tolist(),
        }

        self._latest_result = result
        self._notify_observers(result)
        return result

    def _normalize_signal(self, data: np.ndarray) -> np.ndarray:
        """Normalize signal to [0, 1] range for heuristic fallback and feature display."""
        if len(data) == 0:
            return data
        min_val, max_val = data.min(), data.max()
        if max_val > min_val:
            return (data - min_val) / (max_val - min_val)
        return np.zeros_like(data)

    def _heuristic_estrus_score(self, features: np.ndarray) -> float:
        """
        Simple rule-based estrus probability when ML model is unavailable.
        Based on signal variance and range (activity-based detection).
        """
        if len(features) < 6:
            return 0.0

        std_dev = features[1]  # std
        peak_ptp = features[7]  # peak-to-peak

        # Higher variance and range suggest increased activity (possible estrus)
        score = 0.3 * std_dev + 0.3 * min(peak_ptp, 1.0)
        return min(max(score, 0.0), 1.0)

    # ------------------------------------------------------------------
    # Result access
    # ------------------------------------------------------------------
    @property
    def latest_result(self) -> Optional[Dict[str, Any]]:
        return self._latest_result

    def reset(self) -> None:
        self._latest_result = None
