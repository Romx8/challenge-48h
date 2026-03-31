# Backend Air Map

Backend FastAPI qui relie:
- l'API `data` (pollution + météo + indice)
- PostgreSQL (stockage local pour requêtage rapide)
- le frontend (endpoint filtrable)

## Endpoints

- `GET /health`
- `GET /metrics`
- `POST /api/v1/jobs/sync`
- `GET /api/v1/readings`

## Worker

Le worker tourne toutes les `SYNC_INTERVAL_SECONDS` et exécute:
1. refresh côté data API (`/api/v1/jobs/refresh`)
2. récupération historique (`/api/v1/index/history`)
3. upsert en base (clé unique `station_code + observed_at`)

## Variables principales

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD_FILE`
- `DATA_API_BASE_URL`, `DATA_API_HISTORY_DAYS`
- `SYNC_INTERVAL_SECONDS`, `SYNC_ON_STARTUP`, `ENABLE_SYNC_WORKER`
- `CORS_ORIGINS`

## Lancement local (hors Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8787
```
