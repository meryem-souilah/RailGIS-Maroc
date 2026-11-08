"""Compare Random Forest and XGBoost on chronologically held-out operation records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from data_science.features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_training_targets,
    source_type,
)
from data_science.quality import clean_training_rows


def _models() -> dict:
    try:
        from xgboost import XGBRegressor
    except ImportError as exc:
        raise RuntimeError(
            "XGBoost manque. Installez les dépendances avec "
            "`pip install -r data_science/requirements.txt`."
        ) from exc

    return {
        "random_forest": RandomForestRegressor(
            n_estimators=250,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
        "xgboost": XGBRegressor(
            n_estimators=250,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=42,
            n_jobs=2,
        ),
    }


def _pipeline(regressor) -> Pipeline:
    preprocessing = ColumnTransformer(
        [
            ("categories", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("numeric", "passthrough", NUMERIC_FEATURES),
        ]
    )
    return Pipeline([("features", preprocessing), ("model", regressor)])


def train_models(input_path: Path, output_dir: Path) -> dict:
    rows, data_quality = clean_training_rows(pd.read_csv(input_path))
    provenance = source_type(rows)
    features, targets = build_training_targets(rows)
    if len(features) < 30:
        raise ValueError(
            "Au moins 30 opérations valides sont nécessaires pour comparer les modèles."
        )
    if data_quality["months_covered"] < 2:
        raise ValueError("Les données doivent couvrir au moins deux mois distincts.")

    scheduled = pd.to_datetime(rows["scheduled_datetime"], errors="raise")
    order = scheduled.sort_values(kind="stable").index
    split_at = int(len(order) * 0.8)
    train_indices, test_indices = order[:split_at], order[split_at:]
    if len(train_indices) < 2 or len(test_indices) < 2:
        raise ValueError("Pas assez d'opérations pour séparer apprentissage et test.")

    models = _models()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "data_source": provenance,
        "n_observations": len(rows),
        "split": "chronologique (80 % apprentissage, 20 % test)",
        "data_quality": data_quality,
        "targets": {},
    }
    for target_name, target in targets.items():
        y_train, y_test = target.loc[train_indices], target.loc[test_indices]
        comparisons = {}
        fitted = {}
        for model_name, regressor in models.items():
            estimator = _pipeline(regressor)
            estimator.fit(features.loc[train_indices], y_train)
            prediction = estimator.predict(features.loc[test_indices])
            comparisons[model_name] = {
                "mae": round(float(mean_absolute_error(y_test, prediction)), 3),
                "rmse": round(float(mean_squared_error(y_test, prediction) ** 0.5), 3),
                "r2": (
                    round(float(r2_score(y_test, prediction)), 3) if y_test.nunique() > 1 else None
                ),
            }
            fitted[model_name] = estimator

        winner = min(comparisons, key=lambda name: comparisons[name]["mae"])
        joblib.dump(fitted[winner], output_dir / f"{target_name}.joblib")
        report["targets"][target_name] = {
            "unit": "minutes" if target_name == "delay_minutes" else "passagers",
            "winner_by_test_mae": winner,
            "test_metrics": comparisons,
        }

    report["delay_alert_threshold_minutes"] = max(
        15.0, float(targets["delay_minutes"].iloc[train_indices].quantile(0.9))
    )
    report["passenger_reference_p90"] = float(
        targets["passenger_count"].iloc[train_indices].quantile(0.9)
    )
    report["warning"] = (
        "Données synthétiques fictives : métriques et prédictions non représentatives du réseau."
        if provenance == "synthetic_demo"
        else "Origine des données fournie par l'utilisateur et non vérifiée."
    )
    with (output_dir / "metrics.json").open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV d'opérations enrichies")
    parser.add_argument("--output-dir", type=Path, default=Path("models/trained"))
    args = parser.parse_args()
    report = train_models(args.input, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
