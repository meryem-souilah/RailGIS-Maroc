"""Validation and feature engineering shared by training and prediction."""

from __future__ import annotations

import pandas as pd

CATEGORICAL_FEATURES = ["line_id", "station_id"]
NUMERIC_FEATURES = [
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "is_holiday",
    "temperature_c",
    "precipitation_mm",
    "wind_speed_kmh",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES
WEATHER_COLUMNS = ["temperature_c", "precipitation_mm", "wind_speed_kmh"]


def _boolean_series(values: pd.Series, column: str) -> pd.Series:
    normalized = values.astype(str).str.strip().str.lower()
    parsed = normalized.map(
        {
            "true": 1,
            "1": 1,
            "1.0": 1,
            "yes": 1,
            "false": 0,
            "0": 0,
            "0.0": 0,
            "no": 0,
        }
    )
    if parsed.isna().any():
        raise ValueError(f"La colonne {column} doit contenir true/false ou 1/0.")
    return parsed.astype(int)


def build_features(rows: pd.DataFrame) -> pd.DataFrame:
    """Build model inputs from scheduled times, station/line IDs and weather."""
    required = ["scheduled_datetime", "line_id", "station_id", *WEATHER_COLUMNS, "is_holiday"]
    missing = [column for column in required if column not in rows.columns]
    if missing:
        raise ValueError(f"Colonnes requises manquantes : {', '.join(missing)}")

    scheduled = pd.to_datetime(rows["scheduled_datetime"], errors="raise")
    if scheduled.isna().any():
        raise ValueError("scheduled_datetime ne peut pas contenir de valeur vide.")

    features = pd.DataFrame(index=rows.index)
    for column in CATEGORICAL_FEATURES:
        if rows[column].isna().any():
            raise ValueError(f"La colonne {column} ne peut pas contenir de valeur vide.")
        features[column] = rows[column].astype(str)

    features["hour"] = scheduled.dt.hour
    features["day_of_week"] = scheduled.dt.dayofweek
    features["month"] = scheduled.dt.month
    features["is_weekend"] = (scheduled.dt.dayofweek >= 5).astype(int)
    features["is_holiday"] = _boolean_series(rows["is_holiday"], "is_holiday")
    for column in WEATHER_COLUMNS:
        features[column] = pd.to_numeric(rows[column], errors="coerce")
        if features[column].isna().any():
            raise ValueError(f"La colonne {column} doit contenir des valeurs numériques.")

    return features[FEATURE_COLUMNS]


def build_training_targets(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Validate labels and calculate delay in minutes from actual vs scheduled time."""
    required = ["actual_datetime", "passenger_count"]
    missing = [column for column in required if column not in rows.columns]
    if missing:
        raise ValueError(f"Colonnes de résultats manquantes : {', '.join(missing)}")

    features = build_features(rows)
    scheduled = pd.to_datetime(rows["scheduled_datetime"], errors="raise")
    actual = pd.to_datetime(rows["actual_datetime"], errors="raise")
    if scheduled.isna().any() or actual.isna().any():
        raise ValueError("Les heures planifiées et réelles ne peuvent pas être vides.")

    passengers = pd.to_numeric(rows["passenger_count"], errors="coerce")
    if passengers.isna().any() or (passengers < 0).any():
        raise ValueError("passenger_count doit contenir des nombres positifs ou nuls.")

    delay_minutes = (actual - scheduled).dt.total_seconds() / 60
    return features, {
        "delay_minutes": delay_minutes,
        "passenger_count": passengers,
    }


def source_type(rows: pd.DataFrame) -> str:
    """Return a cautious provenance label and reject mixed synthetic/real data."""
    if "is_synthetic" not in rows.columns:
        return "user_provided_unverified"

    flags = _boolean_series(rows["is_synthetic"], "is_synthetic")
    if flags.empty or flags.eq(1).all():
        return "synthetic_demo"
    if flags.eq(1).any():
        raise ValueError("Ne mélangez pas les lignes synthétiques et les données réelles.")
    return "user_provided_unverified"
