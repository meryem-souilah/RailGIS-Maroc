import json
import os
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from data_science.predict import predict_rows

MODEL_DIR = Path(
    os.environ.get(
        "MODEL_DIR",
        str(Path(__file__).resolve().parents[2] / "models" / "trained"),
    )
)
MODEL_FILES = ("delay_minutes.joblib", "passenger_count.joblib", "metrics.json")


def get_prediction_status() -> dict:
    missing = [name for name in MODEL_FILES if not (MODEL_DIR / name).is_file()]
    if missing:
        return {
            "available": False,
            "missing_files": missing,
            "message": "Entraînez les modèles et placez les fichiers dans MODEL_DIR.",
        }

    with (MODEL_DIR / "metrics.json").open(encoding="utf-8") as file:
        report = json.load(file)
    return {
        "available": True,
        "data_source": report["data_source"],
        "warning": report["warning"],
        "targets": report["targets"],
        "trained_on": report["n_observations"],
    }


def predict_observations(observations: list[BaseModel]) -> dict:
    status = get_prediction_status()
    if not status["available"]:
        raise FileNotFoundError(status["message"])

    rows = pd.DataFrame([item.model_dump() for item in observations])
    result = predict_rows(rows, MODEL_DIR)
    report = result["report"]
    predictions = []
    for row in result["predictions"].to_dict(orient="records"):
        row["scheduled_datetime"] = row["scheduled_datetime"].isoformat()
        predictions.append(
            {
                "scheduled_datetime": row["scheduled_datetime"],
                "line_id": row["line_id"],
                "station_id": row["station_id"],
                "retard_minutes": float(row["prediction_retard_minutes"]),
                "passagers": int(row["prediction_passagers"]),
                "recommandations": row["recommandations"].split(" | "),
            }
        )

    return {
        "data_source": report["data_source"],
        "warning": report["warning"],
        "predictions": predictions,
    }
