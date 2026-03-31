from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret(path: str | None) -> str | None:
    if not path:
        return None
    secret_path = Path(path)
    if not secret_path.exists():
        return None
    return secret_path.read_text(encoding="utf-8").strip() or None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="challenge-48h-backend", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_port: int = Field(default=8787, alias="APP_PORT")

    db_host: str = Field(default="postgres-primary", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="air_map", alias="DB_NAME")
    db_user: str = Field(default="air_map_app", alias="DB_USER")
    db_password: str | None = Field(default=None, alias="DB_PASSWORD")
    db_password_file: str | None = Field(default=None, alias="DB_PASSWORD_FILE")

    data_api_base_url: str = Field(default="http://data-api:8000", alias="DATA_API_BASE_URL")
    data_api_history_days: int = Field(default=10, alias="DATA_API_HISTORY_DAYS")
    data_api_timeout_seconds: int = Field(default=60, alias="DATA_API_TIMEOUT_SECONDS")
    data_api_refresh_on_sync: bool = Field(default=True, alias="DATA_API_REFRESH_ON_SYNC")

    enable_sync_worker: bool = Field(default=True, alias="ENABLE_SYNC_WORKER")
    sync_on_startup: bool = Field(default=True, alias="SYNC_ON_STARTUP")
    sync_interval_seconds: int = Field(default=300, alias="SYNC_INTERVAL_SECONDS")

    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @computed_field(return_type=str)
    @property
    def db_resolved_password(self) -> str:
        return self.db_password or _read_secret(self.db_password_file) or ""

    @computed_field(return_type=str)
    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_resolved_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @computed_field(return_type=list[str])
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
