#!/bin/sh
set -eu

run_compose() {
  if command -v docker >/dev/null 2>&1 && docker buildx version >/dev/null 2>&1; then
    docker compose "$@"
  else
    DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose "$@"
  fi
}

if [ -f .env ]; then
  run_compose --env-file .env up --build "$@"
else
  run_compose up --build "$@"
fi
