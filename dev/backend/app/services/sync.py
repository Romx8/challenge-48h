from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timezone

from app.core.settings import Settings
from app.db.repository import Repository
from app.services.data_client import DataApiClient
from app.services.metrics import SYNC_FAILURE_TOTAL, SYNC_LAST_TS, SYNC_ROWS_TOTAL, SYNC_SUCCESS_TOTAL

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, settings: Settings, repository: Repository):
        self.settings = settings
        self.repository = repository
        self.data_client = DataApiClient(settings)

    def sync_once(self) -> tuple[int, datetime]:
        self.data_client.refresh()
        records = self.data_client.fetch_history()
        rows = self.repository.upsert_readings(records)
        synced_at = datetime.now(timezone.utc)

        SYNC_SUCCESS_TOTAL.inc()
        SYNC_ROWS_TOTAL.inc(rows)
        SYNC_LAST_TS.set(synced_at.timestamp())

        return rows, synced_at

    def ensure_date_range_loaded(self, start_date: date, end_date: date) -> tuple[int, int]:
        if start_date > end_date:
            raise ValueError("start_date doit être <= end_date")

        missing_days = self.repository.get_uncovered_dates(start_date, end_date)
        if not missing_days:
            return 0, 0

        fetch_start = missing_days[0]
        fetch_end = missing_days[-1]
        self.data_client.refresh_range(fetch_start, fetch_end)
        records = self.data_client.fetch_history_range(fetch_start, fetch_end)

        rows = self.repository.upsert_readings(records)
        coverage_counts = _coverage_counts(records)
        self.repository.mark_coverage_for_dates(missing_days, coverage_counts)

        return rows, len(missing_days)


class SyncWorker:
    def __init__(self, sync_service: SyncService, interval_seconds: int):
        self.sync_service = sync_service
        self.interval_seconds = max(10, interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="data-sync-worker", daemon=True)
        self._thread.start()
        logger.info("Worker de synchronisation démarré (interval=%ss)", self.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                rows, synced_at = self.sync_service.sync_once()
                logger.info("Synchronisation réussie: %s lignes (%s)", rows, synced_at.isoformat())
            except Exception as exc:
                SYNC_FAILURE_TOTAL.inc()
                logger.exception("Erreur de synchronisation: %s", exc)

            elapsed = time.monotonic() - started
            wait_time = max(0.0, self.interval_seconds - elapsed)
            self._stop_event.wait(wait_time)


def normalize_date_range(start_date: date | None, end_date: date | None) -> tuple[date | None, date | None]:
    if start_date is None and end_date is None:
        return None, None
    if start_date is None:
        return end_date, end_date
    if end_date is None:
        return start_date, start_date
    return start_date, end_date


def _coverage_counts(records: list[dict]) -> dict[date, int]:
    counts: dict[date, int] = {}
    for record in records:
        observed_raw = record.get("observed_at")
        if not observed_raw:
            continue
        observed_at = _parse_observed_at(observed_raw)
        observed_day = observed_at.astimezone(timezone.utc).date()
        counts[observed_day] = counts.get(observed_day, 0) + 1
    return counts


def _parse_observed_at(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    raise ValueError(f"Valeur observed_at invalide: {value!r}")
