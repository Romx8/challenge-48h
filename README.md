# Challenge 48h - Unified Dev/Data/Infra Platform

Plateforme unifiée pour:
- visualiser les données pollution/météo sur carte
- piloter les services Docker
- centraliser le monitoring (Prometheus, Grafana, Blackbox)

---

## Quick Start

```bash
git clone https://github.com/Romx8/challenge-48h.git
cd challenge-48h
cp .env.example .env
docker compose --env-file .env up --build
```

Puis ouvrir:
- Hub UI: `http://localhost:8501`
- Webapp Dev: `http://localhost:5173`
- Backend Dev: `http://localhost:8787`
- Data API: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

---

## Prérequis

1. Docker Desktop (inclut Docker Engine + Compose)
   - Installation: https://docs.docker.com/desktop/
2. Git
   - Installation: https://git-scm.com/downloads

Option Linux (sans Docker Desktop):
- Docker Engine: https://docs.docker.com/engine/install/
- Docker Compose plugin: https://docs.docker.com/compose/install/linux/

---

## Stack Technique

- Frontend dev: React + Vite + Leaflet
- Backend dev: FastAPI + PostgreSQL
- API data: FastAPI
- Observabilité: Prometheus + Grafana + Blackbox + cAdvisor + Docker Exporter
- Orchestration: Docker Compose
- Hub central: Streamlit

---

## Commandes utiles

Lancer en arrière-plan + checks:

```bash
./run-detached.sh
```

Lancer en mode compatible environnements sans `buildx`:

```bash
./run.sh
```

Vérifier la santé de la stack:

```bash
./scripts/check-stack.sh .env
```

---

## Structure

- `dev/` : frontend + backend du projet dev
- `data/` : API data
- `hub-ui/` : interface Streamlit centralisée
- `infra/monitoring/` : Prometheus, Grafana, Blackbox, exporters
- `docker-compose.yml` : orchestration unique

