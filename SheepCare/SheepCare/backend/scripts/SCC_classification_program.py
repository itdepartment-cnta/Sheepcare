"""Manually invoke the milk quality (SCC) model on an input Excel file.

Standalone helper script, not used by the app pipeline (see
backend/core/spectral_model.py and backend/core/spectral_parser.py for the
production inference path). Reads the NIR spectral columns from the input
Excel, runs the trained model, and writes the predictions to an output Excel.
"""
import argparse
import os
import numpy as np
import pandas as pd
import joblib
from sklearn.base import BaseEstimator, TransformerMixin
from scipy.signal import savgol_filter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # backend/scripts -> backend -> SheepCare
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "milk_quality_scc.joblib")

FEATURE_RANGE = (643.75, 1048.36)
LABELS = {0: "Lower", 1: "Upper"}


# ========================
# Spectral preprocessing transformers
#
# These must stay defined in __main__ (i.e. in this script, not imported
# from elsewhere): the model.joblib pipeline was pickled with these classes
# living in __main__, so joblib.load() below can only resolve them if this
# script is run directly as the main module.
# ========================

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
            axis=1
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually run the milk quality (SCC) model over a spectral readings Excel file."
    )
    parser.add_argument(
        "input_excel",
        help="Path to the input Excel file with the spectral readings (column 'id' + wavelength columns).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path for the output Excel with predictions (default: predicciones.xlsx next to the input file).",
    )
    args = parser.parse_args()

    output_path = args.output or os.path.join(
        os.path.dirname(os.path.abspath(args.input_excel)), "predicciones.xlsx"
    )

    # Load the model already shipped with the project (see backend/core/spectral_model.py).
    model = joblib.load(MODEL_PATH)

    # Load readings and select the wavelength sub-range the model was trained on.
    datos_raw = pd.read_excel(args.input_excel)
    low, high = FEATURE_RANGE
    X_filtrado = datos_raw.loc[:, low:high]
    X_filtrado = X_filtrado.dropna()
    X_filtrado = 2.0 - np.log10(X_filtrado)  # convert to absorbance values

    y_pred = model.predict(X_filtrado).ravel()
    labels = np.vectorize(LABELS.get)(y_pred)

    datos_raw["predictions"] = labels
    datos_raw.to_excel(output_path, index=False)
    print(f"Predictions saved to: {output_path}")


if __name__ == "__main__":
    main()
