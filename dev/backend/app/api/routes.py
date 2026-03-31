from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response

from app.core.container import repository, settings, sync_service
from app.models.schemas import HealthResponse, ReadingsMeta, ReadingsResponse, SyncResponse
from app.services.metrics import render_metrics
from app.services.sync import normalize_date_range

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@router.get("/metrics")
def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


@router.post("/api/v1/jobs/sync", response_model=SyncResponse)
def run_sync() -> SyncResponse:
    try:
        rows, synced_at = sync_service.sync_once()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur sync: {exc}") from exc

    return SyncResponse(status="synced", rows=rows, syncedAt=synced_at)


@router.get("/api/v1/readings", response_model=ReadingsResponse)
def get_readings(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    min_lat: float | None = Query(default=None),
    max_lat: float | None = Query(default=None),
    min_lng: float | None = Query(default=None),
    max_lng: float | None = Query(default=None),
    min_index: float | None = Query(default=None, ge=0, le=100),
    max_index: float | None = Query(default=None, ge=0, le=100),
    aggregate_by: str = Query(default="none", pattern="^(none|city)$"),
    limit: int = Query(default=300, ge=1, le=2000),
) -> ReadingsResponse:
    resolved_start_date, resolved_end_date = normalize_date_range(start_date, end_date)

    if resolved_start_date and resolved_end_date and resolved_start_date > resolved_end_date:
        raise HTTPException(status_code=400, detail="start_date doit être <= end_date")

    if min_lat is not None and max_lat is not None and min_lat > max_lat:
        raise HTTPException(status_code=400, detail="min_lat doit être <= max_lat")

    if min_lng is not None and max_lng is not None and min_lng > max_lng:
        raise HTTPException(status_code=400, detail="min_lng doit être <= max_lng")

    if min_index is not None and max_index is not None and min_index > max_index:
        raise HTTPException(status_code=400, detail="min_index doit être <= max_index")

    try:
        if resolved_start_date and resolved_end_date:
            sync_service.ensure_date_range_loaded(resolved_start_date, resolved_end_date)

        total, items = repository.fetch_readings(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
            min_index=min_index,
            max_index=max_index,
            aggregate_by=aggregate_by,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur lecture DB: {exc}") from exc

    now_utc = datetime.now(timezone.utc)
    filters = {
        "start_date": resolved_start_date.isoformat() if resolved_start_date else None,
        "end_date": resolved_end_date.isoformat() if resolved_end_date else None,
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lng": min_lng,
        "max_lng": max_lng,
        "min_index": min_index,
        "max_index": max_index,
        "aggregate_by": aggregate_by,
        "limit": limit,
    }

    meta = ReadingsMeta(
        total=total,
        returned=len(items),
        mode=aggregate_by,
        generatedAt=now_utc,
        filters=filters,
    )
    return ReadingsResponse(items=items, meta=meta)
