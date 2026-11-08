"""Generate clearly labelled, fictional operation records for a reproducible demo."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATIONS = ROOT / "data" / "processed" / "gares.geojson"
DEFAULT_LINES = ROOT / "data" / "processed" / "lignes.geojson"
DEFAULT_OUTPUT = ROOT / "data" / "demo" / "operations_synthetiques.csv"
FIELDS = [
    "scheduled_datetime",
    "actual_datetime",
    "station_id",
    "station_name",
    "line_id",
    "latitude",
    "longitude",
    "passenger_count",
    "temperature_c",
    "precipitation_mm",
    "wind_speed_kmh",
    "is_holiday",
    "is_synthetic",
]


def _features(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    return payload["features"]


def generate_demo(
    stations_path: Path = DEFAULT_STATIONS,
    lines_path: Path = DEFAULT_LINES,
    output_path: Path = DEFAULT_OUTPUT,
    days: int = 180,
    seed: int = 42,
) -> int:
    stations = _features(stations_path)
    lines = _features(lines_path)
    if not stations or not lines:
        raise ValueError("Les GeoJSON des gares et des lignes doivent contenir des entités.")

    rng = random.Random(seed)
    start = datetime(2025, 1, 1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for day_index in range(days):
            service_day = start + timedelta(days=day_index)
            seasonal_temperature = 19 + 10 * math.sin(2 * math.pi * (day_index - 90) / 365)
            for run_index in range(18):
                station = stations[(day_index * 18 + run_index) % len(stations)]
                line = lines[(day_index + run_index) % len(lines)]
                longitude, latitude = station["geometry"]["coordinates"][:2]
                hour = 6 + (run_index * 17 % 17)
                scheduled = service_day.replace(hour=hour, minute=(run_index % 4) * 15)
                temperature = round(seasonal_temperature + rng.uniform(-5, 5), 1)
                precipitation = round(rng.choices([0, rng.uniform(0.1, 15)], [0.83, 0.17])[0], 1)
                wind = round(rng.uniform(3, 35), 1)
                is_weekend = service_day.weekday() >= 5
                is_holiday = int(rng.random() < 0.025)
                rush_hour = int(hour in (7, 8, 17, 18, 19))
                delay = max(
                    0,
                    round(
                        2
                        + 4 * rush_hour
                        + precipitation * 0.7
                        + wind * 0.08
                        + rng.gauss(0, 4)
                        + (rng.uniform(10, 35) if rng.random() < 0.12 else 0)
                    ),
                )
                passengers = max(
                    5,
                    round(
                        45
                        + 60 * rush_hour
                        + (25 if line["properties"].get("type_ligne") == "LGV" else 0)
                        - (20 if is_weekend else 0)
                        + rng.gauss(0, 22)
                    ),
                )
                writer.writerow(
                    {
                        "scheduled_datetime": scheduled.isoformat(timespec="minutes"),
                        "actual_datetime": (scheduled + timedelta(minutes=delay)).isoformat(
                            timespec="minutes"
                        ),
                        "station_id": station["properties"]["id"],
                        "station_name": station["properties"]["nom"],
                        "line_id": line["properties"]["id"],
                        "latitude": latitude,
                        "longitude": longitude,
                        "passenger_count": passengers,
                        "temperature_c": temperature,
                        "precipitation_mm": precipitation,
                        "wind_speed_kmh": wind,
                        "is_holiday": is_holiday,
                        "is_synthetic": "true",
                    }
                )
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.days < 30:
        parser.error("--days doit être au moins égal à 30.")
    count = generate_demo(output_path=args.output, days=args.days, seed=args.seed)
    print(f"{count} opérations FICTIVES écrites dans {args.output}. Ne pas les utiliser en réel.")


if __name__ == "__main__":
    main()
