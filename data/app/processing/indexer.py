from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.core.config import Settings
from app.utils.geo import haversine_km


def _row_modifier(row: pd.Series) -> float:
    modifier = 1.0
    wind = row.get("wind_speed_ms")
    humidity = row.get("humidity_pct")
    pressure = row.get("pressure_hpa")
    precip = row.get("precip_mm")

    if pd.notna(wind) and wind < 2:
        modifier += 0.10
    if pd.notna(humidity) and humidity > 80:
        modifier += 0.05
    if pd.notna(pressure) and pressure > 1015:
        modifier += 0.05
    if pd.notna(precip) and precip > 1:
        modifier -= 0.10
    if pd.notna(wind) and wind > 6:
        modifier -= 0.10

    return max(0.7, min(1.3, modifier))


def classify_risk(index_value: float) -> str:
    if index_value <= 20:
        return "tres_faible"
    if index_value <= 40:
        return "faible"
    if index_value <= 60:
        return "modere"
    if index_value <= 80:
        return "eleve"
    return "tres_eleve"


def attach_pollution_coordinates(
    pollution_df: pd.DataFrame,
    meteo_stations_df: pd.DataFrame,
    geodair_coords: dict[str, tuple[float, float]],
) -> pd.DataFrame:
    frame = pollution_df.copy()
    station_ref = frame[["station_code", "station_name"]].drop_duplicates()
    station_ref["station_name_key"] = station_ref["station_name"].str.upper().str.replace("-", " ", regex=False)

    meteo_ref = meteo_stations_df.copy()
    meteo_ref["meteo_name_key"] = meteo_ref["meteo_station_name"].astype(str).str.upper().str.replace("-", " ", regex=False)

    rows = []
    for station in station_ref.itertuples(index=False):
        station_code = station.station_code
        lat = None
        lon = None
        source = "unmatched"

        if station_code in geodair_coords:
            lat, lon = geodair_coords[station_code]
            source = "geodair"
        else:
            tokens = [token for token in station.station_name_key.split() if len(token) >= 4]
            match = None
            for token in tokens:
                candidates = meteo_ref[meteo_ref["meteo_name_key"].str.contains(token, na=False, regex=False)]
                if not candidates.empty:
                    match = candidates.iloc[0]
                    break
            if match is not None:
                lat = float(match["meteo_latitude"])
                lon = float(match["meteo_longitude"])
                source = "heuristic_meteo_name"

        rows.append(
            {
                "station_code": station_code,
                "latitude": lat,
                "longitude": lon,
                "coord_source": source,
            }
        )

    coords = pd.DataFrame(rows)
    frame = frame.merge(coords, on="station_code", how="left")
    return frame.dropna(subset=["latitude", "longitude"])


def match_nearest_meteo_station(
    pollution_df: pd.DataFrame,
    meteo_stations_df: pd.DataFrame,
    max_distance_km: float,
) -> pd.DataFrame:
    station_coords = pollution_df[["station_code", "latitude", "longitude"]].drop_duplicates()
    meteo_coords = meteo_stations_df[["meteo_station_code", "meteo_station_name", "meteo_latitude", "meteo_longitude"]]

    matches = []
    for row in station_coords.itertuples(index=False):
        best_code = None
        best_name = None
        best_distance = math.inf
        for meteo in meteo_coords.itertuples(index=False):
            distance = haversine_km(row.latitude, row.longitude, meteo.meteo_latitude, meteo.meteo_longitude)
            if distance < best_distance:
                best_distance = distance
                best_code = meteo.meteo_station_code
                best_name = meteo.meteo_station_name

        if best_code is not None and best_distance <= max_distance_km:
            matches.append(
                {
                    "station_code": row.station_code,
                    "matched_meteo_station_code": best_code,
                    "matched_meteo_station": best_name,
                    "station_distance_km": round(best_distance, 3),
                }
            )

    match_df = pd.DataFrame(matches)
    if match_df.empty:
        return pollution_df.iloc[0:0].copy()
    return pollution_df.merge(match_df, on="station_code", how="inner")


def align_temporal_data(pollution_df: pd.DataFrame, meteo_df: pd.DataFrame) -> pd.DataFrame:
    left = pollution_df.sort_values("observed_at")
    right = meteo_df.sort_values("observed_at")

    merged = pd.merge_asof(
        left,
        right,
        by="matched_meteo_station_code",
        on="observed_at",
        direction="nearest",
        tolerance=pd.Timedelta("3h"),
    )
    return merged


def compute_index(df: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    frame = df.copy()

    pollutant_score_components = []
    for pollutant, weight in settings.pollution_weights.items():
        ref = settings.pollution_reference_ugm3[pollutant]
        if pollutant not in frame.columns:
            frame[pollutant] = np.nan
        ratio = (frame[pollutant].clip(lower=0) / ref) * 100
        weighted = ratio.clip(upper=100) * weight
        pollutant_score_components.append(weighted)

    frame["pollution_score"] = np.nansum(pollutant_score_components, axis=0)
    frame["meteo_modifier"] = frame.apply(_row_modifier, axis=1)
    frame["index"] = (frame["pollution_score"] * frame["meteo_modifier"]).clip(upper=100).round(2)
    frame["risk_level"] = frame["index"].map(classify_risk)
    return frame
