from __future__ import annotations

import re

import numpy as np
import pandas as pd


POLLUTANT_ALIASES = {
    "no2": "no2",
    "no": "no",
    "nox_as_no2": "nox",
    "o3": "o3",
    "pm10": "pm10",
    "pm2_5": "pm25",
    "pm25": "pm25",
    "so2": "so2",
    "co": "co",
}


def _normalize_pollutant_name(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return POLLUTANT_ALIASES.get(key, key)


def clean_pollution(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame["observed_at"] = pd.to_datetime(frame["date_de_debut"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["observed_at", "code_site", "polluant"])

    frame["station_code"] = frame["code_site"].astype(str).str.strip()
    frame["station_name"] = frame["nom_site"].astype(str).str.strip()
    frame["pollutant"] = frame["polluant"].map(_normalize_pollutant_name)
    frame["value"] = pd.to_numeric(frame["valeur"], errors="coerce")

    frame = frame.dropna(subset=["value"])
    frame.loc[frame["value"] < 0, "value"] = np.nan

    frame = frame[["station_code", "station_name", "observed_at", "pollutant", "value"]]
    frame = frame.drop_duplicates(subset=["station_code", "observed_at", "pollutant"], keep="last")

    pivot = (
        frame.pivot_table(
            index=["station_code", "station_name", "observed_at"],
            columns="pollutant",
            values="value",
            aggfunc="mean",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    for col in ("no2", "o3", "pm10", "pm25", "so2", "co"):
        if col not in pivot.columns:
            pivot[col] = np.nan

    return pivot


def clean_meteo(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame["observed_at"] = pd.to_datetime(frame["validity_time"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["observed_at", "geo_id_wmo"])

    frame["meteo_station_code"] = frame["geo_id_wmo"].astype(str).str.zfill(5)
    frame["temperature_c"] = pd.to_numeric(frame.get("t"), errors="coerce") - 273.15
    frame["humidity_pct"] = pd.to_numeric(frame.get("u"), errors="coerce")
    frame["wind_speed_ms"] = pd.to_numeric(frame.get("ff"), errors="coerce")
    frame["pressure_hpa"] = pd.to_numeric(frame.get("pmer"), errors="coerce") / 100.0

    precip_col = None
    for candidate in ("rr1", "rr3", "rr6", "rr12", "rr24"):
        if candidate in frame.columns:
            precip_col = candidate
            break
    frame["precip_mm"] = pd.to_numeric(frame.get(precip_col), errors="coerce")

    keep_cols = [
        "meteo_station_code",
        "observed_at",
        "temperature_c",
        "humidity_pct",
        "wind_speed_ms",
        "pressure_hpa",
        "precip_mm",
    ]
    frame = frame[keep_cols]
    frame = frame.drop_duplicates(subset=["meteo_station_code", "observed_at"], keep="last")
    return frame
