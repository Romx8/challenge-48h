from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["tres_faible", "faible", "modere", "eleve", "tres_eleve"]


class PollutantsPayload(BaseModel):
    no2: float | None = None
    o3: float | None = None
    pm10: float | None = None
    pm25: float | None = None
    so2: float | None = None
    co: float | None = None


class MeteoPayload(BaseModel):
    temperature_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_ms: float | None = None
    pressure_hpa: float | None = None
    precip_mm: float | None = None


class ConsolidatedIndexRecord(BaseModel):
    station_code: str
    latitude: float
    longitude: float
    observed_at: datetime
    index: float = Field(ge=0, le=100)
    pollution_score: float | None = Field(default=None, ge=0, le=100)
    meteo_modifier: float | None = None
    risk_level: RiskLevel
    pollutants: PollutantsPayload
    meteo: MeteoPayload
    matched_meteo_station: str | None = None
    station_distance_km: float | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str


class RefreshResponse(BaseModel):
    status: Literal["refreshed"]
    rows: int
    generated_at: datetime
