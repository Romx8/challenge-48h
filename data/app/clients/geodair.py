from __future__ import annotations

from dataclasses import dataclass

import requests

from app.core.config import Settings


@dataclass(slots=True)
class GeodairStation:
    station_code: str
    latitude: float
    longitude: float


class GeodairClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.geodair_base_url.rstrip("/")
        self.api_key = settings.geodair_api_key
        self.timeout = 20

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, path: str) -> list[dict]:
        if not self.enabled:
            return []

        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=self.timeout)
            if response.status_code >= 400:
                return []
            payload = response.json()
        except Exception:
            return []

        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "results", "items"):
                maybe = payload.get(key)
                if isinstance(maybe, list):
                    return maybe
        return []

    @staticmethod
    def _extract_station_code(row: dict) -> str | None:
        for key in ("code site", "code_site", "station_code", "code", "id"):
            value = row.get(key)
            if value:
                return str(value).strip()
        return None

    @staticmethod
    def _extract_coords(row: dict) -> tuple[float | None, float | None]:
        lat_keys = ("latitude", "lat", "y")
        lon_keys = ("longitude", "lon", "lng", "x")
        lat = None
        lon = None
        for key in lat_keys:
            value = row.get(key)
            if value not in (None, ""):
                try:
                    lat = float(value)
                    break
                except Exception:
                    pass
        for key in lon_keys:
            value = row.get(key)
            if value not in (None, ""):
                try:
                    lon = float(value)
                    break
                except Exception:
                    pass
        return lat, lon

    def fetch_station_coordinates(self) -> dict[str, GeodairStation]:
        if not self.enabled:
            return {}

        candidate_paths = [
            "stations",
            "sites",
            "referentials/stations",
            "v1/stations",
        ]
        stations: dict[str, GeodairStation] = {}
        for path in candidate_paths:
            rows = self._request(path)
            for row in rows:
                station_code = self._extract_station_code(row)
                lat, lon = self._extract_coords(row)
                if station_code and lat is not None and lon is not None:
                    stations[station_code] = GeodairStation(
                        station_code=station_code,
                        latitude=lat,
                        longitude=lon,
                    )
            if stations:
                break
        return stations
