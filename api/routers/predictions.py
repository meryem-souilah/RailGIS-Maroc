from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.prediction_service import get_prediction_status, predict_observations

router = APIRouter(prefix="/predictions", tags=["predictions"])


class Observation(BaseModel):
    scheduled_datetime: datetime
    line_id: str = Field(min_length=1, max_length=100)
    station_id: str = Field(min_length=1, max_length=100)
    temperature_c: float = Field(allow_inf_nan=False)
    precipitation_mm: float = Field(ge=0, allow_inf_nan=False)
    wind_speed_kmh: float = Field(ge=0, allow_inf_nan=False)
    is_holiday: bool


class PredictionRequest(BaseModel):
    observations: list[Observation] = Field(min_length=1, max_length=200)


@router.get("/status")
def prediction_status():
    return get_prediction_status()


@router.post("")
def create_predictions(request: PredictionRequest):
    try:
        return predict_observations(request.observations)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
