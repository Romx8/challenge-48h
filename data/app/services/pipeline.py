from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from app.clients.datagouv import DataGouvClient
from app.clients.geodair import GeodairClient
from app.core.config import Settings
from app.dataio.loaders import (
    load_meteo_raw_datagouv,
    load_meteo_raw_datagouv_range,
    load_meteo_stations_raw,
    load_meteo_stations_raw_datagouv,
    load_pollution_raw_datagouv,
    load_pollution_raw_datagouv_range,
)
from app.processing.cleaning import clean_meteo, clean_pollution
from app.processing.indexer import (
    align_temporal_data,
    attach_pollution_coordinates,
    compute_index,
    match_nearest_meteo_station,
)


@dataclass
class PipelineResult:
    rows: int
    generated_at: datetime


class ConsolidationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.datagouv_client = DataGouvClient(settings)
        self.geodair_client = GeodairClient(settings)
        self._cache_df: pd.DataFrame | None = None
        self._generated_at: datetime | None = None

    def _load_data_for_range(self, start_date: date | None, end_date: date | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if start_date is not None and end_date is not None:
            return (
                load_pollution_raw_datagouv_range(self.settings, self.datagouv_client, start_date, end_date),
                load_meteo_raw_datagouv_range(self.settings, self.datagouv_client, start_date, end_date),
                load_meteo_stations_raw_datagouv(self.settings, self.datagouv_client),
            )

        return (
            load_pollution_raw_datagouv(self.settings, self.datagouv_client),
            load_meteo_raw_datagouv(self.settings, self.datagouv_client),
            load_meteo_stations_raw_datagouv(self.settings, self.datagouv_client),
        )

    def refresh(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        days: int | None = None,
    ) -> PipelineResult:
        if start_date is None and end_date is None and days is not None:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=max(1, days) - 1)
        elif start_date is not None and end_date is None:
            end_date = start_date
        elif end_date is not None and start_date is None:
            start_date = end_date

        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date doit être <= end_date")

        pollution_raw, meteo_raw, meteo_stations_raw = self._load_data_for_range(start_date, end_date)

        pollution_clean = clean_pollution(pollution_raw)
        meteo_clean = clean_meteo(meteo_raw)

        geodair_map = {
            code: (station.latitude, station.longitude)
            for code, station in self.geodair_client.fetch_station_coordinates().items()
        }

        pollution_with_coords = attach_pollution_coordinates(
            pollution_df=pollution_clean,
            meteo_stations_df=meteo_stations_raw,
            geodair_coords=geodair_map,
        )
        pollution_with_station = match_nearest_meteo_station(
            pollution_df=pollution_with_coords,
            meteo_stations_df=meteo_stations_raw,
            max_distance_km=self.settings.max_spatial_distance_km,
        )

        meteo_for_merge = meteo_clean.rename(columns={"meteo_station_code": "matched_meteo_station_code"})
        merged = align_temporal_data(pollution_with_station, meteo_for_merge)
        scored = compute_index(merged, self.settings)

        final = scored[
            [
                "station_code",
                "latitude",
                "longitude",
                "observed_at",
                "index",
                "pollution_score",
                "meteo_modifier",
                "risk_level",
                "no2",
                "o3",
                "pm10",
                "pm25",
                "so2",
                "co",
                "temperature_c",
                "humidity_pct",
                "wind_speed_ms",
                "pressure_hpa",
                "precip_mm",
                "matched_meteo_station",
                "station_distance_km",
            ]
        ].copy()

        final = final.drop_duplicates(subset=["station_code", "observed_at"], keep="last")
        final = final.sort_values("observed_at")

        final.to_parquet(self.settings.cache_file, index=False)
        self._cache_df = final
        self._generated_at = datetime.now(timezone.utc)

        return PipelineResult(rows=len(final), generated_at=self._generated_at)

    def _load_cache_if_needed(self) -> None:
        if self._cache_df is not None:
            return
        if self.settings.cache_file.exists():
            self._cache_df = pd.read_parquet(self.settings.cache_file)
            self._cache_df["observed_at"] = pd.to_datetime(self._cache_df["observed_at"], utc=True)
            self._generated_at = datetime.now(timezone.utc)
        else:
            self.refresh()

    def get_history(self, days: int = 10, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        if start_date is not None or end_date is not None:
            self.refresh(start_date=start_date, end_date=end_date)
        else:
            self._load_cache_if_needed()

        assert self._cache_df is not None

        if start_date is not None and end_date is None:
            end_date = start_date
        if end_date is not None and start_date is None:
            start_date = end_date

        if start_date is not None and end_date is not None:
            min_ts = pd.Timestamp(start_date).tz_localize("UTC")
            max_ts = pd.Timestamp(end_date).tz_localize("UTC") + pd.Timedelta(days=1)
            history = self._cache_df[
                (self._cache_df["observed_at"] >= min_ts) & (self._cache_df["observed_at"] < max_ts)
            ].copy()
            return history.sort_values("observed_at")

        max_dt = self._cache_df["observed_at"].max()
        if pd.isna(max_dt):
            return self._cache_df.iloc[0:0]

        min_dt = max_dt - pd.Timedelta(days=days)
        history = self._cache_df[self._cache_df["observed_at"] >= min_dt].copy()
        return history.sort_values("observed_at")

    def get_latest(self) -> pd.DataFrame:
        self._load_cache_if_needed()
        assert self._cache_df is not None

        latest_ts = self._cache_df["observed_at"].max()
        latest = self._cache_df[self._cache_df["observed_at"] == latest_ts].copy()
        return latest.sort_values("station_code")
