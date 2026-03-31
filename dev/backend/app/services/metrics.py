from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

SYNC_SUCCESS_TOTAL = Counter("backend_sync_success_total", "Nombre de synchronisations réussies")
SYNC_FAILURE_TOTAL = Counter("backend_sync_failure_total", "Nombre de synchronisations en erreur")
SYNC_ROWS_TOTAL = Counter("backend_sync_rows_total", "Nombre total de lignes upsertées")
SYNC_LAST_TS = Gauge("backend_sync_last_timestamp_seconds", "Timestamp Unix de la dernière sync réussie")
HTTP_REQUESTS_TOTAL = Counter(
    "backend_http_requests_total",
    "Nombre total de requêtes HTTP backend",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "backend_http_request_duration_seconds",
    "Durée des requêtes HTTP backend",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def observe_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    status = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(max(0.0, duration_seconds))


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
