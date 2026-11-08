"""Join historical weather and Moroccan public-holiday data to operation records."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd
import requests

WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
HOLIDAYS_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/MA"
TIMEZONE = "Africa/Casablanca"


def _as_local_hour(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(TIMEZONE).tz_localize(None)
    return timestamp.floor("h").strftime("%Y-%m-%dT%H:00")


def _weather_for_location(
    latitude: float, longitude: float, start: date, end: date
) -> dict[str, dict[str, float]]:
    response = requests.get(
        WEATHER_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": "temperature_2m,precipitation,wind_speed_10m",
            "timezone": TIMEZONE,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    hourly = payload.get("hourly", {})
    required = {
        "time",
        "temperature_2m",
        "precipitation",
        "wind_speed_10m",
    }
    if not required.issubset(hourly):
        raise ValueError(f"Réponse météo Open-Meteo incomplète pour {latitude}, {longitude}.")
    lengths = {len(hourly[column]) for column in required}
    if len(lengths) != 1:
        raise ValueError(f"Réponse météo Open-Meteo incohérente pour {latitude}, {longitude}.")

    weather = {}
    for timestamp, temperature, precipitation, wind in zip(
        hourly["time"],
        hourly["temperature_2m"],
        hourly["precipitation"],
        hourly["wind_speed_10m"],
    ):
        if temperature is not None and precipitation is not None and wind is not None:
            weather[_as_local_hour(timestamp)] = {
                "temperature_c": float(temperature),
                "precipitation_mm": float(precipitation),
                "wind_speed_kmh": float(wind),
            }
    return weather


def _moroccan_holidays(years: set[int]) -> set[str]:
    holidays = set()
    for year in sorted(years):
        response = requests.get(
            HOLIDAYS_URL.format(year=year),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise TypeError(f"Réponse calendrier invalide pour l'année {year}.")
        holidays.update(item["date"] for item in payload if "date" in item)
    return holidays


def enrich_rows(rows: pd.DataFrame) -> pd.DataFrame:
    required = ["scheduled_datetime", "station_id", "latitude", "longitude"]
    missing = [column for column in required if column not in rows.columns]
    if missing:
        raise ValueError(f"Colonnes requises manquantes : {', '.join(missing)}")
    if rows.empty:
        raise ValueError("Le fichier d'exploitation ne contient aucune ligne.")

    enriched = rows.copy()
    scheduled = pd.to_datetime(enriched["scheduled_datetime"], errors="raise")
    if scheduled.isna().any():
        raise ValueError("scheduled_datetime ne peut pas contenir de valeur vide.")
    enriched["latitude"] = pd.to_numeric(enriched["latitude"], errors="coerce")
    enriched["longitude"] = pd.to_numeric(enriched["longitude"], errors="coerce")
    if enriched[["latitude", "longitude"]].isna().any().any():
        raise ValueError("Les coordonnées de chaque gare doivent être numériques.")

    start = scheduled.min().date()
    end = scheduled.max().date()
    location_weather: dict[tuple[float, float], dict[str, dict[str, float]]] = {}
    for latitude, longitude in (
        enriched[["latitude", "longitude"]].drop_duplicates().itertuples(index=False, name=None)
    ):
        location_weather[(latitude, longitude)] = _weather_for_location(
            latitude, longitude, start, end
        )

    holiday_dates = _moroccan_holidays(set(scheduled.dt.year))
    temperatures, rain, wind, holiday_flags = [], [], [], []
    for row_index, timestamp in scheduled.items():
        row = enriched.loc[row_index]
        hour = _as_local_hour(timestamp)
        observation = location_weather[(row["latitude"], row["longitude"])].get(hour)
        if observation is None:
            raise ValueError(f"Pas de météo historique pour la gare {row['station_id']} à {hour}.")
        temperatures.append(observation["temperature_c"])
        rain.append(observation["precipitation_mm"])
        wind.append(observation["wind_speed_kmh"])
        holiday_flags.append(int(timestamp.strftime("%Y-%m-%d") in holiday_dates))

    enriched["temperature_c"] = temperatures
    enriched["precipitation_mm"] = rain
    enriched["wind_speed_kmh"] = wind
    enriched["is_holiday"] = holiday_flags
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV des opérations ONCF")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/operations_enrichies.csv"),
        help="CSV de sortie enrichi",
    )
    args = parser.parse_args()

    rows = pd.read_csv(args.input)
    enriched = enrich_rows(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(args.output, index=False)
    print(f"{len(enriched)} opérations enrichies dans {args.output}")


if __name__ == "__main__":
    main()
