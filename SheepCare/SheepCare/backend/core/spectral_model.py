"""
MilkQualityLoader - Loads and runs the milk quality (SCC) NIR spectral model.

Separate from ModelsLoader: this model is a scikit-learn Pipeline (not a
single estimator), uses .predict() instead of .predict_proba() (no
confidence score available), and needs its own custom transformer classes
available at unpickle time.
"""

import sys
import numpy as np
import pandas as pd
from typing import List, Optional
from sklearn.base import BaseEstimator, TransformerMixin
from scipy.signal import savgol_filter

from .models_loader import resolve_models_dir

MODEL_FILENAME = "milk_quality_scc.joblib"

LABELS = {0: "Lower", 1: "Upper"}


class SNVTransformer(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        mu = X.mean(axis=1, keepdims=True)
        sd = X.std(axis=1, keepdims=True)
        sd[sd == 0] = 1.0
        return (X - mu) / sd


class SavGolTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, window_length=7, polyorder=2, deriv=0):
        self.window_length = window_length
        self.polyorder = polyorder
        self.deriv = deriv

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        return savgol_filter(
            X,
            window_length=self.window_length,
            polyorder=self.polyorder,
            deriv=self.deriv,
            axis=1,
        )


def _register_main_module_classes() -> None:
    """
    The model.joblib pipeline was pickled with SNVTransformer/SavGolTransformer
    defined in `__main__` (it was trained via a standalone script). joblib's
    unpickler resolves classes by their original module, so without this it
    fails with `AttributeError: Can't get attribute 'SNVTransformer' on
    <module '__main__'>` regardless of how the backend is started.
    """
    main_module = sys.modules["__main__"]
    main_module.SNVTransformer = SNVTransformer
    main_module.SavGolTransformer = SavGolTransformer


class MilkQualityLoader:
    """Loads the milk quality Pipeline and runs inference."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._model_path = model_path or self._default_model_path()
        self._model = None
        self._load_model()

    @staticmethod
    def _default_model_path() -> str:
        import os
        return os.path.join(resolve_models_dir(), MODEL_FILENAME)

    def _load_model(self) -> None:
        import os
        if not os.path.exists(self._model_path):
            return
        _register_main_module_classes()
        import joblib
        self._model = joblib.load(self._model_path)

    def predict(self, X: pd.DataFrame) -> List[str]:
        """Predict "Lower"/"Upper" labels for a batch of feature rows."""
        if self._model is None:
            raise RuntimeError(f"Milk quality model not loaded from {self._model_path}")
        y_pred = self._model.predict(X).ravel()
        return [LABELS.get(int(v), str(v)) for v in y_pred]

    @property
    def model_path(self) -> str:
        return self._model_path

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
