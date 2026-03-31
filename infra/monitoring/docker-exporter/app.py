from __future__ import annotations

import os
import threading
import time
from typing import Any

import docker
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

app = FastAPI(title="docker-exporter", version="1.0.0")
client = docker.from_env()
refresh_interval = max(5, int(os.getenv("DOCKER_EXPORTER_REFRESH_INTERVAL_SECONDS", "20")))
_cache_lock = threading.Lock()
_metrics_cache: bytes = b""
_refresh_thread: threading.Thread | None = None
_stop_event = threading.Event()
_stack_name = ""


def _detect_stack_name() -> str:
    configured = os.getenv("STACK_NAME", "").strip()
    if configured:
        return configured

    container_id = os.getenv("HOSTNAME", "").strip()
    if not container_id:
        return ""

    try:
        me = client.containers.get(container_id)
    except Exception:
        return ""

    labels = me.labels or {}
    return labels.get("com.docker.compose.project", "").strip()


def _cpu_percent(stats: dict[str, Any]) -> float:
    cpu_stats = stats.get("cpu_stats", {})
    precpu_stats = stats.get("precpu_stats", {})

    cpu_total = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
    precpu_total = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
    cpu_delta = cpu_total - precpu_total

    system_total = cpu_stats.get("system_cpu_usage", 0)
    presystem_total = precpu_stats.get("system_cpu_usage", 0)
    system_delta = system_total - presystem_total

    online_cpus = cpu_stats.get("online_cpus") or len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", []) or [])
    if cpu_delta <= 0 or system_delta <= 0 or online_cpus <= 0:
        return 0.0

    return max(0.0, (cpu_delta / system_delta) * online_cpus * 100.0)


def _memory_bytes(stats: dict[str, Any]) -> float:
    memory_stats = stats.get("memory_stats", {})
    usage = float(memory_stats.get("usage", 0.0) or 0.0)
    cache = float(memory_stats.get("stats", {}).get("cache", 0.0) or 0.0)
    value = usage - cache
    return max(0.0, value)


def _memory_percent(stats: dict[str, Any], memory_bytes: float) -> float:
    memory_stats = stats.get("memory_stats", {})
    limit = float(memory_stats.get("limit", 0.0) or 0.0)
    if limit <= 0:
        return 0.0
    return max(0.0, min(100.0, (memory_bytes / limit) * 100.0))


def _collect_metrics_payload() -> bytes:
    registry = CollectorRegistry()

    up_gauge = Gauge(
        "docker_service_up",
        "Etat du conteneur (1=running, 0=stopped)",
        ["stack", "service", "container", "state"],
        registry=registry,
    )
    cpu_gauge = Gauge(
        "docker_service_cpu_percent",
        "Utilisation CPU en pourcentage par conteneur",
        ["stack", "service", "container"],
        registry=registry,
    )
    memory_bytes_gauge = Gauge(
        "docker_service_memory_bytes",
        "Utilisation RAM en bytes par conteneur",
        ["stack", "service", "container"],
        registry=registry,
    )
    memory_percent_gauge = Gauge(
        "docker_service_memory_percent",
        "Utilisation RAM en pourcentage par conteneur",
        ["stack", "service", "container"],
        registry=registry,
    )
    scrape_success = Gauge(
        "docker_exporter_scrape_success",
        "Indique si le scrape Docker a reussi (1) ou echoue (0)",
        registry=registry,
    )

    stack_name = _stack_name
    filters: dict[str, Any] = {}
    if stack_name:
        filters = {"label": f"com.docker.compose.project={stack_name}"}

    try:
        containers = client.containers.list(all=True, filters=filters)
    except Exception:
        scrape_success.set(0)
        return generate_latest(registry)

    for container in containers:
        labels = container.labels or {}
        service = labels.get("com.docker.compose.service", container.name)
        state = container.status or "unknown"
        up_value = 1.0 if state == "running" else 0.0

        up_gauge.labels(
            stack=stack_name or "default",
            service=service,
            container=container.name,
            state=state,
        ).set(up_value)

        cpu_percent = 0.0
        memory_bytes = 0.0
        memory_percent = 0.0
        if state == "running":
            try:
                stats = container.stats(stream=False)
                cpu_percent = _cpu_percent(stats)
                memory_bytes = _memory_bytes(stats)
                memory_percent = _memory_percent(stats, memory_bytes)
            except Exception:
                cpu_percent = 0.0
                memory_bytes = 0.0
                memory_percent = 0.0

        cpu_gauge.labels(stack=stack_name or "default", service=service, container=container.name).set(cpu_percent)
        memory_bytes_gauge.labels(
            stack=stack_name or "default",
            service=service,
            container=container.name,
        ).set(memory_bytes)
        memory_percent_gauge.labels(
            stack=stack_name or "default",
            service=service,
            container=container.name,
        ).set(memory_percent)

    scrape_success.set(1)
    return generate_latest(registry)


def _refresh_metrics_cache() -> None:
    global _metrics_cache

    payload = _collect_metrics_payload()
    with _cache_lock:
        _metrics_cache = payload


def _refresh_loop() -> None:
    while not _stop_event.is_set():
        try:
            _refresh_metrics_cache()
        except Exception:
            # Never crash background exporter loop on runtime collection errors.
            pass
        _stop_event.wait(refresh_interval)


@app.on_event("startup")
def on_startup() -> None:
    global _refresh_thread, _stack_name
    _stack_name = _detect_stack_name()
    _stop_event.clear()
    _refresh_thread = threading.Thread(target=_refresh_loop, name="docker-exporter-refresh", daemon=True)
    _refresh_thread.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    _stop_event.set()
    if _refresh_thread and _refresh_thread.is_alive():
        _refresh_thread.join(timeout=5)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "stack": _stack_name or "default"}


@app.get("/metrics")
def metrics() -> Response:
    payload = b""
    with _cache_lock:
        payload = _metrics_cache

    if not payload:
        _refresh_metrics_cache()
        with _cache_lock:
            payload = _metrics_cache

    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
