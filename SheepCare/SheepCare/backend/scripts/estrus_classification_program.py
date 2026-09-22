"""Manually invoke the estrus classification model on an input Excel file.

Standalone helper script, not used by the app pipeline (see backend/core/engine.py
for the production inference path). Reads two reading columns from the input
Excel, runs the trained model, and writes the predictions to an output Excel.
"""
import argparse
import os
import pandas as pd
import joblib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # backend/scripts -> backend -> SheepCare
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "estrus_clasification.joblib")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually run the estrus classification model over a readings Excel file."
    )
    parser.add_argument(
        "input_excel",
        help="Path to the input Excel file with the readings (columns B and C).",
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

    # Load the model already shipped with the project (see backend/core/models_loader.py).
    model = joblib.load(MODEL_PATH)

    # Load readings and keep only the two feature columns the model expects.
    conductometria = pd.read_excel(args.input_excel)
    X_data = conductometria.iloc[:, 1:3]

    predictions = model.predict(X_data)
    conductometria["predictions"] = predictions
    conductometria.to_excel(output_path, index=False)
    print(f"Predictions saved to: {output_path}")


if __name__ == "__main__":
    main()
