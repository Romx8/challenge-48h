from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
import re

import pandas as pd
import requests

from app.core.config import Settings


class DataGouvClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.timeout = 60
        self._synop_resource_cache: dict[int, str] = {}

    def _download_bytes(self, url: str) -> bytes:
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def _object_api_get(self, path: str, params: dict[str, str] | None = None) -> dict:
        base = self.settings.datagouv_object_api_base_url.rstrip("/")
        url = f"{base}/{path.lstrip('/')}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _looks_like_gzip(content: bytes) -> bool:
        return len(content) >= 2 and content[0] == 0x1F and content[1] == 0x8B

    def fetch_pollution_df(self) -> pd.DataFrame:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=max(1, self.settings.datagouv_pollution_days) - 1)
        return self.fetch_pollution_df_for_range(start_date=start_date, end_date=end_date)

    def fetch_pollution_df_for_range(self, start_date: date, end_date: date) -> pd.DataFrame:
        if start_date > end_date:
            raise ValueError("start_date doit être <= end_date")

        bucket = self.settings.datagouv_object_bucket
        pattern = re.compile(r"FR_E2_(\d{4}-\d{2}-\d{2})\.csv$")
        csv_objects: list[tuple[str, str]] = []

        for year in range(start_date.year, end_date.year + 1):
            prefix = f"{self.settings.datagouv_pollution_prefix.strip('/')}/{year}/"
            listing = self._object_api_get(
                f"buckets/{bucket}/objects",
                params={"prefix": prefix, "recursive": "true", "limit": "5000"},
            )
            objects = listing.get("objects", [])
            for obj in objects:
                name = str(obj.get("name", ""))
                match = pattern.search(name)
                if not match:
                    continue
                file_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                if start_date <= file_date <= end_date:
                    csv_objects.append((name, match.group(1)))

        if not csv_objects:
            raise ValueError("Aucun fichier pollution CSV E2 trouvé via Data.gouv Object API")

        csv_objects.sort(key=lambda item: item[1])
        frames = []
        for object_name, _ in csv_objects:
            payload = self._download_bytes(
                f"{self.settings.datagouv_object_api_base_url.rstrip('/')}/"
                f"buckets/{bucket}/objects/download?prefix={object_name}"
            )
            try:
                frame = pd.read_csv(BytesIO(payload), sep=";", quotechar='"', low_memory=False, encoding="utf-8-sig")
            except UnicodeDecodeError:
                frame = pd.read_csv(BytesIO(payload), sep=";", quotechar='"', low_memory=False, encoding="latin-1")
            frame["source_file"] = object_name.split("/")[-1]
            frames.append(frame)

        return pd.concat(frames, ignore_index=True)

    def _synop_resource_url_for_year(self, year: int) -> str:
        if year in self._synop_resource_cache:
            return self._synop_resource_cache[year]

        dataset_url = self.settings.datagouv_synop_dataset_api_url
        response = requests.get(dataset_url, timeout=self.timeout)
        response.raise_for_status()
        dataset = response.json()

        target = f"synop_{year}"
        for resource in dataset.get("resources", []):
            title = str(resource.get("title", "")).strip().lower()
            if title == target:
                url = str(resource.get("latest") or resource.get("url") or "").strip()
                if not url:
                    break
                self._synop_resource_cache[year] = url
                return url

        raise ValueError(f"Ressource SYNOP introuvable pour l'année {year} sur Data.gouv")

    def fetch_synop_df(self, start_date: date, end_date: date) -> pd.DataFrame:
        if start_date > end_date:
            raise ValueError("start_date doit être <= end_date")

        frames = []
        for year in range(start_date.year, end_date.year + 1):
            url = self._synop_resource_url_for_year(year)
            content = self._download_bytes(url)
            compression = "gzip" if self._looks_like_gzip(content) else "infer"
            frame = pd.read_csv(BytesIO(content), sep=";", low_memory=False, compression=compression)
            frames.append(frame)

        merged = pd.concat(frames, ignore_index=True)
        merged["validity_time"] = pd.to_datetime(merged["validity_time"], errors="coerce", utc=True)
        time_mask = (
            merged["validity_time"] >= pd.Timestamp(start_date).tz_localize("UTC") - pd.Timedelta(hours=3)
        ) & (merged["validity_time"] <= pd.Timestamp(end_date).tz_localize("UTC") + pd.Timedelta(days=1, hours=3))
        return merged[time_mask].copy()

    def fetch_synop_stations_df(self) -> pd.DataFrame:
        content = self._download_bytes(self.settings.datagouv_synop_stations_resource_url)
        return pd.read_json(BytesIO(content))
