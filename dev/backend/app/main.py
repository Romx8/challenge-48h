from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.container import repository, settings, sync_service, worker
from app.services.metrics import observe_http_request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def prometheus_http_metrics(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed = time.perf_counter() - started
        observe_http_request(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_seconds=elapsed,
        )


@app.on_event("startup")
def on_startup() -> None:
    repository.init_schema()
    if settings.sync_on_startup:
        try:
            rows, synced_at = sync_service.sync_once()
            logger.info("Synchronisation initiale OK: %s lignes (%s)", rows, synced_at.isoformat())
        except Exception:
            logger.exception("Synchronisation initiale en erreur")

    if settings.enable_sync_worker:
        worker.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    worker.stop()
