"""
ModelsLoader - Handles loading and running ML models (scikit-learn & ONNX).
Reused from the original SHEEPCARE MVP.
"""

import os
import sys
import numpy as np
from typing import Optional, Any


class ModelsLoader:
    """
    Loads pre-trained ML models from disk and runs inference.
    Supports:
    - scikit-learn models (.pkl / .joblib)
    - ONNX models (.onnx)
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._model_path = model_path or self._default_model_path()
        self._model: Any = None
        self._onnx_session: Any = None
        self._load_model()

    @staticmethod
    def _log(msg: str) -> None:
        try:
            import os as _os
            log = _os.path.join(_os.environ.get("APPDATA", ""), "SheepCare", "model_load.log")
            with open(log, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    @staticmethod
    def _default_model_path() -> str:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            meipass = getattr(sys, "_MEIPASS", None)
            ModelsLoader._log(f"frozen=True  exe_dir={exe_dir}  _MEIPASS={meipass}")
            # Try both locations: _internal/models (PyInstaller 6.x) and exe/models
            for candidate in [
                os.path.join(exe_dir, "_internal", "models"),
                meipass and os.path.join(meipass, "models"),
                os.path.join(exe_dir, "models"),
            ]:
                if candidate and os.path.exists(candidate):
                    ModelsLoader._log(f"model_dir found: {candidate}")
                    return candidate
            fallback = os.path.join(exe_dir, "_internal", "models")
            ModelsLoader._log(f"no candidate found, fallback: {fallback}")
            return fallback
        # Desarrollo: subir 3 niveles desde backend/core/models_loader.py
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        return os.path.join(base_dir, "models")

    def _load_model(self) -> None:
        """
        Attempt to load a model from the models directory.
        Tries .joblib, .pkl, and .onnx formats.
        """
        ModelsLoader._log(f"_load_model path={self._model_path}  exists={os.path.exists(self._model_path)}")
        if not os.path.exists(self._model_path):
            return  # No model directory yet

        if os.path.isfile(self._model_path):
            # Direct file path
            self._load_from_file(self._model_path)
        else:
            # Directory - search for model files
            for ext in [".joblib", ".pkl", ".onnx"]:
                for fname in os.listdir(self._model_path):
                    if fname.endswith(ext):
                        self._load_from_file(os.path.join(self._model_path, fname))
                        return

    def _load_from_file(self, file_path: str) -> None:
        """Load a model from a specific file."""
        ModelsLoader._log(f"_load_from_file: {file_path}")
        try:
            if file_path.endswith(".onnx"):
                import onnxruntime as ort
                self._onnx_session = ort.InferenceSession(file_path)
                ModelsLoader._log("onnx loaded OK")
            else:
                import joblib
                self._model = joblib.load(file_path)
                ModelsLoader._log(f"joblib loaded OK: {type(self._model)}")
        except Exception as e:
            ModelsLoader._log(f"LOAD FAILED: {type(e).__name__}: {e}")
            self._model = None
            self._onnx_session = None

    def predict(self, features: np.ndarray) -> Optional[float]:
        """
        Run inference on the model.

        El modelo `estrus_clasification.joblib` usa predict_proba que
        devuelve [prob_clase1, prob_clase2] por fila, donde:
          - clase 1 = No celo
          - clase 2 = Celo
        Se devuelve la probabilidad de clase 2 (Celo).

        Args:
            features: 1-D numpy array of readings (5 valores por animal).

        Returns:
            Probability of estrus/Celo (0.0 - 1.0), or None if no model loaded.
        """
        if self._onnx_session is not None:
            return self._predict_onnx(features)
        elif self._model is not None:
            return self._predict_sklearn(features)
        return None

    def _predict_sklearn(self, features: np.ndarray) -> float:
        """Run inference with a scikit-learn model.

        Usa predict_proba para obtener la probabilidad real de cada clase:
          - proba[0][0] = probabilidad de No celo (clase 1)
          - proba[0][1] = probabilidad de Celo (clase 2)
        Retorna la probabilidad de Celo.
        """
        X = features.reshape(1, -1)

        # predict_proba devuelve [[prob_clase1, prob_clase2]]
        proba = self._model.predict_proba(X)
        # Devolver probabilidad de clase 2 (Celo)
        return float(proba[0][1]) if proba.shape[1] > 1 else float(proba[0][0])

    def _predict_onnx(self, features: np.ndarray) -> float:
        """Run inference with an ONNX model."""
        if self._onnx_session is None:
            return 0.0

        input_name = self._onnx_session.get_inputs()[0].name
        X = features.reshape(1, -1).astype(np.float32)
        outputs = self._onnx_session.run(None, {input_name: X})
        return (
            float(outputs[0][0][1])
            if len(outputs[0].shape) > 1
            else float(outputs[0][0])
        )

    @property
    def model_path(self) -> str:
        return self._model_path

    @model_path.setter
    def model_path(self, path: str) -> None:
        self._model_path = path
        self._load_model()
