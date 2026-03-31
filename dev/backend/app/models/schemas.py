from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


AggregateMode = Literal["none", "city"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str


class ReadingItem(BaseModel):
    stationCode: str | None = None
    city: str
    latitude: float
    longitude: float
    aqi: float
    measuredAt: datetime
    riskLevel: str | None = None
    sampleSize: int | None = None


class ReadingsMeta(BaseModel):
    total: int
    returned: int
    mode: AggregateMode
    generatedAt: datetime
    filters: dict[str, str | int | float | None]


class ReadingsResponse(BaseModel):
    items: list[ReadingItem]
    meta: ReadingsMeta


class SyncResponse(BaseModel):
    status: Literal["synced"]
    rows: int
    syncedAt: datetime
