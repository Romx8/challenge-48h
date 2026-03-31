from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "challenge-48h-data-api"
    app_env: str = "dev"

    geodair_api_key: str | None = Field(default=None, alias="GEODAIR_API_KEY")
    geodair_base_url: str = Field(default="https://www.geodair.fr/api-ext", alias="GEODAIR_BASE_URL")

    data_source: str = Field(default="datagouv", alias="DATA_SOURCE")
    datagouv_pollution_resource_url: str = Field(
        default="https://www.data.gouv.fr/api/1/datasets/r/157ceed4-ce03-4c7d-9cd7-ae60ea07417b",
        alias="DATAGOUV_POLLUTION_RESOURCE_URL",
    )
    datagouv_synop_dataset_api_url: str = Field(
        default="https://www.data.gouv.fr/api/1/datasets/archive-synop-omm/",
        alias="DATAGOUV_SYNOP_DATASET_API_URL",
    )
    datagouv_synop_stations_resource_url: str = Field(
        default="https://www.data.gouv.fr/api/1/datasets/r/d82625f7-091c-40c5-a4e7-313a2ba5d3ef",
        alias="DATAGOUV_SYNOP_STATIONS_RESOURCE_URL",
    )
    datagouv_object_api_base_url: str = Field(
        default="https://object.infra.data.gouv.fr/api/v1",
        alias="DATAGOUV_OBJECT_API_BASE_URL",
    )
    datagouv_object_bucket: str = Field(default="ineris-prod", alias="DATAGOUV_OBJECT_BUCKET")
    datagouv_pollution_prefix: str = Field(
        default="lcsqa/concentrations-de-polluants-atmospheriques-reglementes/temps-reel",
        alias="DATAGOUV_POLLUTION_PREFIX",
    )
    datagouv_pollution_days: int = Field(default=10, alias="DATAGOUV_POLLUTION_DAYS")

    pollution_dir: Path = Path("data/raw/pollution/2026")
    meteo_file: Path = Path("data/raw/meteo/synop_2026.csv")
    meteo_stations_file: Path = Path("data/raw/meteo/stations/postes_synop.geojson")
    processed_dir: Path = Path("data/processed")
    cache_file: Path = Path("data/processed/consolidated_index.parquet")

    max_spatial_distance_km: float = 80.0

    pollution_reference_ugm3: dict[str, float] = {
        "pm25": 25.0,
        "pm10": 45.0,
        "no2": 80.0,
        "o3": 100.0,
        "so2": 125.0,
        "co": 10000.0,
    }
    pollution_weights: dict[str, float] = {
        "pm25": 0.30,
        "pm10": 0.25,
        "no2": 0.20,
        "o3": 0.15,
        "so2": 0.05,
        "co": 0.05,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    return settings
