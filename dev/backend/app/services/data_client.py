from __future__ import annotations

from datetime import date

import httpx

from app.core.settings import Settings


class DataApiClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.data_api_base_url.rstrip("/")
        self.timeout = settings.data_api_timeout_seconds
        self.history_days = settings.data_api_history_days
        self.refresh_on_sync = settings.data_api_refresh_on_sync

    def refresh(self) -> None:
        if not self.refresh_on_sync:
            return
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/v1/jobs/refresh",
                params={"days": self.history_days},
            )
            response.raise_for_status()

    def refresh_range(self, start_date: date, end_date: date) -> None:
        if not self.refresh_on_sync:
            return
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/v1/jobs/refresh",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )
            response.raise_for_status()

    def fetch_history(self) -> list[dict]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/v1/index/history",
                params={"days": self.history_days},
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("Réponse history invalide: liste attendue")
        return payload

    def fetch_history_range(self, start_date: date, end_date: date) -> list[dict]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/v1/index/history",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("Réponse history invalide: liste attendue")
        return payload
