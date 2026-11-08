"""Predict delays/passenger counts and emit transparent rule-based recommendations."""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from data_science.features import build_features


@lru_cache(maxsize=8)
def _load_model(path: str, modified_ns: int):
    return joblib.load(path)


def predict_rows(rows: pd.DataFrame, model_dir: Path) -> dict:
    report_path = model_dir / "metrics.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Rapport de modèles introuvable : {report_path}")
    model_paths = {
        "delay_minutes": model_dir / "delay_minutes.joblib",
        "passenger_count": model_dir / "passenger_count.joblib",
    }
    missing_models = [str(path) for path in model_paths.values() if not path.exists()]
    if missing_models:
        raise FileNotFoundError(f"Modèles de prédiction introuvables : {', '.join(missing_models)}")

    with report_path.open(encoding="utf-8") as file:
        report = json.load(file)

    features = build_features(rows)
    delay_path = model_paths["delay_minutes"]
    passenger_path = model_paths["passenger_count"]
    delay_model = _load_model(str(delay_path), delay_path.stat().st_mtime_ns)
    passenger_model = _load_model(str(passenger_path), passenger_path.stat().st_mtime_ns)
    delays = delay_model.predict(features)
    passengers = passenger_model.predict(features).clip(0, None)

    output = rows.copy()
    output["prediction_retard_minutes"] = delays.round(1)
    output["prediction_passagers"] = passengers.round().astype(int)
    output["recommandations"] = [
        " | ".join(recommendations(delay, count, report))
        for delay, count in zip(delays, passengers)
    ]
    output["source_modele"] = report["data_source"]
    if report["data_source"] == "synthetic_demo":
        output["avertissement"] = (
            "Démonstration synthétique : ne pas utiliser pour une décision réelle."
        )
    return {"report": report, "predictions": output}


def recommendations(delay: float, passengers: float, report: dict) -> list[str]:
    advice = []
    delay_limit = report["delay_alert_threshold_minutes"]
    passenger_limit = report["passenger_reference_p90"]
    if delay >= delay_limit:
        advice.append(
            f"Retard prévu élevé (seuil historique du modèle : {delay_limit:.0f} min) : "
            "vérifier les contraintes et informer l'équipe d'exploitation."
        )
    if passengers >= passenger_limit:
        advice.append(
            f"Fréquentation prévue élevée (au moins le P90 du jeu d'entraînement : "
            f"{passenger_limit:.0f}) : examiner la capacité disponible et un éventuel renfort."
        )
    if not advice:
        advice.append("Aucune alerte selon les seuils du modèle ; conserver le suivi habituel.")
    return advice


def predict(input_path: Path, model_dir: Path, output_path: Path) -> int:
    rows = pd.read_csv(input_path)
    result = predict_rows(rows, model_dir)
    output = result["predictions"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    return len(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV d'opérations à prévoir")
    parser.add_argument("--model-dir", type=Path, default=Path("models/trained"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/previsions_et_recommandations.csv"),
    )
    args = parser.parse_args()
    count = predict(args.input, args.model_dir, args.output)
    print(f"{count} prévisions écrites dans {args.output}")


if __name__ == "__main__":
    main()
