from __future__ import annotations

from app.core.settings import get_settings
from app.db.repository import Repository
from app.services.sync import SyncService, SyncWorker

settings = get_settings()
repository = Repository(settings)
sync_service = SyncService(settings, repository)
worker = SyncWorker(sync_service, settings.sync_interval_seconds)
