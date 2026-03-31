from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.models.schemas import ConsolidatedIndexRecord, HealthResponse, RefreshResponse
from app.services.pipeline import ConsolidationService

router = APIRouter()

settings = get_settings()
service = ConsolidationService(settings)


def _to_records(df: pd.DataFrame) -> list[ConsolidatedIndexRecord]:
    records = []
    for row in df.to_dict(orient="records"):
        observed_at = row.get("observed_at")
        if isinstance(observed_at, pd.Timestamp):
            observed_at = observed_at.to_pydatetime()

        records.append(
            ConsolidatedIndexRecord(
                station_code=row["station_code"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                observed_at=observed_at,
                index=float(row["index"]),
                pollution_score=float(row["pollution_score"]) if pd.notna(row.get("pollution_score")) else None,
                meteo_modifier=float(row["meteo_modifier"]) if pd.notna(row.get("meteo_modifier")) else None,
                risk_level=row["risk_level"],
                pollutants={
                    "no2": float(row["no2"]) if pd.notna(row.get("no2")) else None,
                    "o3": float(row["o3"]) if pd.notna(row.get("o3")) else None,
                    "pm10": float(row["pm10"]) if pd.notna(row.get("pm10")) else None,
                    "pm25": float(row["pm25"]) if pd.notna(row.get("pm25")) else None,
                    "so2": float(row["so2"]) if pd.notna(row.get("so2")) else None,
                    "co": float(row["co"]) if pd.notna(row.get("co")) else None,
                },
                meteo={
                    "temperature_c": float(row["temperature_c"]) if pd.notna(row.get("temperature_c")) else None,
                    "humidity_pct": float(row["humidity_pct"]) if pd.notna(row.get("humidity_pct")) else None,
                    "wind_speed_ms": float(row["wind_speed_ms"]) if pd.notna(row.get("wind_speed_ms")) else None,
                    "pressure_hpa": float(row["pressure_hpa"]) if pd.notna(row.get("pressure_hpa")) else None,
                    "precip_mm": float(row["precip_mm"]) if pd.notna(row.get("precip_mm")) else None,
                },
                matched_meteo_station=row.get("matched_meteo_station"),
                station_distance_km=float(row["station_distance_km"]) if pd.notna(row.get("station_distance_km")) else None,
            )
        )
    return records


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@router.get("/api/v1/index/latest", response_model=list[ConsolidatedIndexRecord])
def latest() -> list[ConsolidatedIndexRecord]:
    try:
        df = service.get_latest()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur pipeline latest: {exc}") from exc
    return _to_records(df)


@router.get("/api/v1/index/history", response_model=list[ConsolidatedIndexRecord])
def history(
    days: int = Query(default=10, ge=1, le=30),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> list[ConsolidatedIndexRecord]:
    try:
        df = service.get_history(days=days, start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur pipeline history: {exc}") from exc
    return _to_records(df)


@router.post("/api/v1/jobs/refresh", response_model=RefreshResponse)
def refresh(
    days: int | None = Query(default=None, ge=1, le=30),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> RefreshResponse:
    try:
        result = service.refresh(start_date=start_date, end_date=end_date, days=days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur refresh: {exc}") from exc
    return RefreshResponse(status="refreshed", rows=result.rows, generated_at=result.generated_at)
