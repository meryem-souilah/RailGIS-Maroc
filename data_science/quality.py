"""Auditable cleanup and data-quality diagnostics for model training inputs."""

from __future__ import annotations

import pandas as pd

from data_science.features import WEATHER_COLUMNS


def _iqr_outlier_count(values: pd.Series) -> int:
    if values.empty:
        return 0
    lower_quartile, upper_quartile = values.quantile([0.25, 0.75])
    spread = upper_quartile - lower_quartile
    if spread == 0:
        return int(values.ne(lower_quartile).sum())
    return int(
        ((values < lower_quartile - 1.5 * spread) | (values > upper_quartile + 1.5 * spread)).sum()
    )


def clean_training_rows(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Drop exact duplicates and rows with invalid required fields; report all exclusions."""
    required = [
        "scheduled_datetime",
        "actual_datetime",
        "line_id",
        "station_id",
        "passenger_count",
        *WEATHER_COLUMNS,
        "is_holiday",
    ]
    missing_columns = [column for column in required if column not in rows.columns]
    if missing_columns:
        raise ValueError(f"Colonnes requises manquantes : {', '.join(missing_columns)}")

    frame = rows.copy().reset_index(drop=True)
    input_rows = len(frame)
    duplicates = int(frame.duplicated().sum())
    frame = frame.drop_duplicates(keep="first").reset_index(drop=True)

    frame["scheduled_datetime"] = pd.to_datetime(frame["scheduled_datetime"], errors="coerce")
    frame["actual_datetime"] = pd.to_datetime(frame["actual_datetime"], errors="coerce")
    for column in ["passenger_count", *WEATHER_COLUMNS]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    normalized_holiday = frame["is_holiday"].astype(str).str.strip().str.lower()
    frame["is_holiday"] = normalized_holiday.map(
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
    valid = (
        frame["scheduled_datetime"].notna()
        & frame["actual_datetime"].notna()
        & frame["line_id"].notna()
        & frame["line_id"].astype(str).str.strip().ne("")
        & frame["station_id"].notna()
        & frame["station_id"].astype(str).str.strip().ne("")
        & frame["passenger_count"].notna()
        & frame["passenger_count"].ge(0)
        & frame["is_holiday"].notna()
    )
    for column in WEATHER_COLUMNS:
        valid &= frame[column].notna()

    if "is_synthetic" in frame.columns:
        normalized_synthetic = frame["is_synthetic"].astype(str).str.strip().str.lower()
        frame["is_synthetic"] = normalized_synthetic.map(
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
        valid &= frame["is_synthetic"].notna()

    excluded_invalid = int((~valid).sum())
    frame = frame.loc[valid].reset_index(drop=True)
    delay_minutes = (frame["actual_datetime"] - frame["scheduled_datetime"]).dt.total_seconds() / 60
    months = frame["scheduled_datetime"].dt.to_period("M").nunique()
    diagnostics = {
        "input_rows": input_rows,
        "exact_duplicates_removed": duplicates,
        "invalid_rows_removed": excluded_invalid,
        "usable_rows": len(frame),
        "months_covered": int(months),
        "delay_iqr_outliers_flagged": _iqr_outlier_count(delay_minutes),
        "passenger_iqr_outliers_flagged": _iqr_outlier_count(frame["passenger_count"]),
        "weather_iqr_outliers_flagged": {
            column: _iqr_outlier_count(frame[column]) for column in WEATHER_COLUMNS
        },
        "outliers_removed": 0,
    }
    return frame, diagnostics
