#!/bin/sh
set -eu

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "[WARN] $ENV_FILE not found, using defaults"
fi

load_var() {
  key="$1"
  default="$2"
  if [ -f "$ENV_FILE" ]; then
    value=$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d '=' -f2- || true)
    if [ -n "${value:-}" ]; then
      echo "$value"
      return
    fi
  fi
  echo "$default"
}

HUB_UI_PORT="$(load_var HUB_UI_PORT 8501)"
FRONTEND_PORT="$(load_var FRONTEND_PORT 5173)"
BACKEND_PORT="$(load_var BACKEND_PORT 8787)"
DATA_API_PORT="$(load_var DATA_API_PORT 8000)"
PROMETHEUS_PORT="$(load_var PROMETHEUS_PORT 9090)"
GRAFANA_PORT="$(load_var GRAFANA_PORT 3000)"
BLACKBOX_PORT="$(load_var BLACKBOX_PORT 9115)"
DOCKER_EXPORTER_PORT="$(load_var DOCKER_EXPORTER_PORT 9324)"

wait_http() {
  name="$1"
  url="$2"
  retries="${3:-40}"
  delay="${4:-3}"

  i=1
  while [ "$i" -le "$retries" ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "[OK] $name -> $url"
      return 0
    fi
    echo "[WAIT] $name ($i/$retries)"
    i=$((i + 1))
    sleep "$delay"
  done

  echo "[ERR] $name unreachable: $url"
  return 1
}

wait_http "Hub UI" "http://localhost:${HUB_UI_PORT}" 60 2
wait_http "Frontend" "http://localhost:${FRONTEND_PORT}" 60 2
wait_http "Backend health" "http://localhost:${BACKEND_PORT}/health" 60 2
wait_http "Data API health" "http://localhost:${DATA_API_PORT}/health" 60 2
wait_http "Prometheus" "http://localhost:${PROMETHEUS_PORT}/-/healthy" 60 2
wait_http "Grafana" "http://localhost:${GRAFANA_PORT}/api/health" 60 2
wait_http "Blackbox" "http://localhost:${BLACKBOX_PORT}/-/healthy" 60 2
wait_http "Docker Exporter" "http://localhost:${DOCKER_EXPORTER_PORT}/health" 60 2

wait_prom_data() {
  url="$1"
  retries="${2:-30}"
  delay="${3:-2}"

  i=1
  while [ "$i" -le "$retries" ]; do
    payload="$(curl -fsS "$url" 2>/dev/null || true)"
    if printf "%s" "$payload" | grep -q '"status":"success"' && printf "%s" "$payload" | grep -q '"result":\[{'; then
      echo "[OK] Prometheus has scraped metrics"
      return 0
    fi
    echo "[WAIT] Prometheus metrics not ready ($i/$retries)"
    i=$((i + 1))
    sleep "$delay"
  done

  echo "[ERR] Prometheus query has no metrics yet"
  return 1
}

wait_prom_data "http://localhost:${PROMETHEUS_PORT}/api/v1/query?query=up" 45 2

echo "[DONE] Stack healthy"
