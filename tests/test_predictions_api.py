import json

from fastapi.testclient import TestClient
from main import app
from routers import predictions
from services import prediction_service

client = TestClient(app)


def test_prediction_status_reports_missing_models(tmp_path, monkeypatch):
    monkeypatch.setattr(prediction_service, "MODEL_DIR", tmp_path)

    response = client.get("/predictions/status")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert set(response.json()["missing_files"]) == {
        "delay_minutes.joblib",
        "passenger_count.joblib",
        "metrics.json",
    }


def test_prediction_route_returns_service_unavailable_without_models(tmp_path, monkeypatch):
    monkeypatch.setattr(prediction_service, "MODEL_DIR", tmp_path)

    response = client.post(
        "/predictions",
        json={
            "observations": [
                {
                    "scheduled_datetime": "2025-01-01T08:00:00",
                    "line_id": "LINE_1",
                    "station_id": "STATION_1",
                    "temperature_c": 20,
                    "precipitation_mm": 0,
                    "wind_speed_kmh": 10,
                    "is_holiday": False,
                }
            ]
        },
    )

    assert response.status_code == 503
    assert "Entraînez les modèles" in response.json()["detail"]


def test_prediction_status_returns_training_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(prediction_service, "MODEL_DIR", tmp_path)
    for filename in prediction_service.MODEL_FILES:
        (tmp_path / filename).touch()
    report = {
        "data_source": "synthetic_demo",
        "warning": "Données fictives.",
        "targets": {},
        "n_observations": 540,
    }
    (tmp_path / "metrics.json").write_text(json.dumps(report), encoding="utf-8")

    response = client.get("/predictions/status")

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["data_source"] == "synthetic_demo"
    assert response.json()["trained_on"] == 540


def test_prediction_route_returns_results(monkeypatch):
    result = {
        "data_source": "synthetic_demo",
        "warning": "Données fictives.",
        "predictions": [
            {
                "scheduled_datetime": "2025-01-01T08:00:00",
                "line_id": "LINE_1",
                "station_id": "STATION_1",
                "retard_minutes": 8.5,
                "passagers": 72,
                "recommandations": ["Aucune alerte."],
            }
        ],
    }
    monkeypatch.setattr(predictions, "predict_observations", lambda observations: result)

    response = client.post(
        "/predictions",
        json={
            "observations": [
                {
                    "scheduled_datetime": "2025-01-01T08:00:00",
                    "line_id": "LINE_1",
                    "station_id": "STATION_1",
                    "temperature_c": 20,
                    "precipitation_mm": 0,
                    "wind_speed_kmh": 10,
                    "is_holiday": False,
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == result


def test_prediction_route_validates_weather_values():
    response = client.post(
        "/predictions",
        json={
            "observations": [
                {
                    "scheduled_datetime": "2025-01-01T08:00:00",
                    "line_id": "LINE_1",
                    "station_id": "STATION_1",
                    "temperature_c": 20,
                    "precipitation_mm": -1,
                    "wind_speed_kmh": 10,
                    "is_holiday": False,
                }
            ]
        },
    )

    assert response.status_code == 422
