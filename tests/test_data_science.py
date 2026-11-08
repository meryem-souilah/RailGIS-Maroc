import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from data_science.make_demo_data import generate_demo

if importlib.util.find_spec("pandas"):
    import pandas as pd

    from data_science.enrich_external import enrich_rows
    from data_science.features import build_features, build_training_targets, source_type
    from data_science.predict import recommendations
    from data_science.quality import clean_training_rows
else:
    pd = None


class DemoDataTests(unittest.TestCase):
    def test_generated_rows_are_marked_synthetic(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "demo.csv"
            count = generate_demo(days=30, output_path=output)
            with output.open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual(count, 30 * 18)
        self.assertEqual(len(rows), count)
        self.assertEqual({row["is_synthetic"] for row in rows}, {"true"})


@unittest.skipIf(pd is None, "Install data_science/requirements.txt to run pandas tests.")
class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.rows = pd.DataFrame(
            {
                "scheduled_datetime": ["2025-01-04T08:30:00", "2025-01-06T09:00:00"],
                "actual_datetime": ["2025-01-04T08:45:00", "2025-01-06T08:58:00"],
                "line_id": ["L1", "L2"],
                "station_id": ["G1", "G2"],
                "passenger_count": [120, 80],
                "temperature_c": [20.5, 18],
                "precipitation_mm": [0, 1.2],
                "wind_speed_kmh": [10, 15],
                "is_holiday": [False, True],
                "is_synthetic": [True, True],
            }
        )

    def test_features_use_scheduled_time_and_calendar(self):
        features = build_features(self.rows)
        self.assertEqual(features.iloc[0]["hour"], 8)
        self.assertEqual(features.iloc[0]["is_weekend"], 1)
        self.assertEqual(features.iloc[1]["is_holiday"], 1)

    def test_training_targets_compute_delay_and_passengers(self):
        _, targets = build_training_targets(self.rows)
        self.assertEqual(targets["delay_minutes"].tolist(), [15, -2])
        self.assertEqual(targets["passenger_count"].tolist(), [120, 80])

    def test_mixed_synthetic_and_unspecified_data_is_rejected(self):
        self.rows.loc[1, "is_synthetic"] = False
        with self.assertRaisesRegex(ValueError, "Ne mélangez pas"):
            source_type(self.rows)

    def test_quality_report_drops_invalid_rows_and_flags_outliers(self):
        damaged = pd.concat(
            [self.rows, self.rows.iloc[[0]], self.rows.iloc[[1]]], ignore_index=True
        )
        damaged.loc[3, "passenger_count"] = -1
        clean, report = clean_training_rows(damaged)
        self.assertEqual(len(clean), 2)
        self.assertEqual(report["exact_duplicates_removed"], 1)
        self.assertEqual(report["invalid_rows_removed"], 1)
        self.assertEqual(report["outliers_removed"], 0)

    def test_quality_cleanup_handles_missing_calendar_flags(self):
        damaged = self.rows.copy()
        damaged["is_holiday"] = damaged["is_holiday"].astype(object)
        damaged.loc[0, "is_holiday"] = None
        clean, report = clean_training_rows(damaged)
        self.assertEqual(report["invalid_rows_removed"], 1)
        self.assertEqual(build_features(clean).iloc[0]["is_holiday"], 1)

    def test_recommendations_use_training_thresholds(self):
        report = {
            "delay_alert_threshold_minutes": 15,
            "passenger_reference_p90": 100,
        }
        advice = recommendations(20, 120, report)
        self.assertEqual(len(advice), 2)
        self.assertIn("Retard prévu élevé", advice[0])

    def test_weather_and_holiday_enrichment(self):
        rows = self.rows.drop(columns=["actual_datetime", "passenger_count", "is_synthetic"])
        rows["latitude"] = 34.0
        rows["longitude"] = -6.0
        weather = {
            "2025-01-04T08:00": {
                "temperature_c": 19.0,
                "precipitation_mm": 0.0,
                "wind_speed_kmh": 8.0,
            },
            "2025-01-06T09:00": {
                "temperature_c": 21.0,
                "precipitation_mm": 0.2,
                "wind_speed_kmh": 9.0,
            },
        }
        with (
            patch("data_science.enrich_external._weather_for_location", return_value=weather),
            patch(
                "data_science.enrich_external._moroccan_holidays",
                return_value={"2025-01-06"},
            ),
        ):
            enriched = enrich_rows(rows)

        self.assertEqual(enriched["temperature_c"].tolist(), [19.0, 21.0])
        self.assertEqual(enriched["is_holiday"].tolist(), [0, 1])


if __name__ == "__main__":
    unittest.main()
