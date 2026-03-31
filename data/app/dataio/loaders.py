from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from app.clients.datagouv import DataGouvClient
from app.core.config import Settings
from app.utils.text import normalize_text


class DataFileMissingError(FileNotFoundError):
    pass


def _assert_exists(path: Path) -> None:
    if not path.exists():
        raise DataFileMissingError(f"Fichier manquant: {path}")


def _pollution_files(pollution_dir: Path) -> list[Path]:
    _assert_exists(pollution_dir)
    files = sorted(pollution_dir.glob("FR_E2_2026-*.csv"))
    if not files:
        raise DataFileMissingError(f"Aucun fichier pollution trouvé dans: {pollution_dir}")
    return files


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: normalize_text(str(col)) for col in df.columns}
    return df.rename(columns=renamed)


def load_pollution_raw(settings: Settings) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for file_path in _pollution_files(settings.pollution_dir):
        frame = pd.read_csv(file_path, sep=";", quotechar='"', low_memory=False)
        frame = _normalize_columns(frame)
        frame["source_file"] = file_path.name
        frames.append(frame)

    df = pd.concat(frames, ignore_index=True)
    required = {"date_de_debut", "code_site", "nom_site", "polluant", "valeur"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes pollution manquantes: {sorted(missing)}")
    return df


def load_pollution_raw_datagouv(settings: Settings, client: DataGouvClient) -> pd.DataFrame:
    df = client.fetch_pollution_df()
    df = _normalize_columns(df)
    required = {"date_de_debut", "code_site", "nom_site", "polluant", "valeur"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes pollution manquantes (Data.gouv): {sorted(missing)}")
    return df


def load_pollution_raw_datagouv_range(
    settings: Settings,
    client: DataGouvClient,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    df = client.fetch_pollution_df_for_range(start_date=start_date, end_date=end_date)
    df = _normalize_columns(df)
    required = {"date_de_debut", "code_site", "nom_site", "polluant", "valeur"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes pollution manquantes (Data.gouv): {sorted(missing)}")
    return df


def load_meteo_raw(settings: Settings) -> pd.DataFrame:
    _assert_exists(settings.meteo_file)
    df = pd.read_csv(settings.meteo_file, sep=";", low_memory=False)
    df = _normalize_columns(df)
    required = {"geo_id_wmo", "validity_time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes meteo manquantes: {sorted(missing)}")
    return df


def load_meteo_raw_datagouv(settings: Settings, client: DataGouvClient) -> pd.DataFrame:
    from datetime import datetime, timedelta

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=max(1, settings.datagouv_pollution_days) - 1)
    df = client.fetch_synop_df(start_date=start_date, end_date=end_date)
    df = _normalize_columns(df)
    required = {"geo_id_wmo", "validity_time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes meteo manquantes (Data.gouv): {sorted(missing)}")
    return df


def load_meteo_raw_datagouv_range(
    settings: Settings,
    client: DataGouvClient,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    df = client.fetch_synop_df(start_date=start_date, end_date=end_date)
    df = _normalize_columns(df)
    required = {"geo_id_wmo", "validity_time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes meteo manquantes (Data.gouv): {sorted(missing)}")
    return df


def load_meteo_stations_raw(settings: Settings) -> pd.DataFrame:
    _assert_exists(settings.meteo_stations_file)
    stations = pd.read_json(settings.meteo_stations_file)
    if "features" not in stations.columns:
        raise ValueError("GeoJSON stations invalide: clé 'features' absente")

    rows = []
    for feature in stations["features"].tolist():
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates", [None, None])
        rows.append(
            {
                "meteo_station_code": str(properties.get("Id", "")).zfill(5),
                "meteo_station_name": properties.get("Nom"),
                "meteo_latitude": coordinates[1] if len(coordinates) > 1 else None,
                "meteo_longitude": coordinates[0] if len(coordinates) > 1 else None,
                "meteo_altitude": properties.get("Altitude"),
            }
        )

    df = pd.DataFrame(rows)
    return df.dropna(subset=["meteo_station_code", "meteo_latitude", "meteo_longitude"])


def load_meteo_stations_raw_datagouv(settings: Settings, client: DataGouvClient) -> pd.DataFrame:
    stations = client.fetch_synop_stations_df()
    if "features" not in stations.columns:
        raise ValueError("GeoJSON stations Data.gouv invalide: clé 'features' absente")

    rows = []
    for feature in stations["features"].tolist():
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates", [None, None])
        rows.append(
            {
                "meteo_station_code": str(properties.get("Id", "")).zfill(5),
                "meteo_station_name": properties.get("Nom"),
                "meteo_latitude": coordinates[1] if len(coordinates) > 1 else None,
                "meteo_longitude": coordinates[0] if len(coordinates) > 1 else None,
                "meteo_altitude": properties.get("Altitude"),
            }
        )

    df = pd.DataFrame(rows)
    return df.dropna(subset=["meteo_station_code", "meteo_latitude", "meteo_longitude"])
