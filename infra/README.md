# Infra unifiée (dev + data + backend + monitoring)

Cette infra fusionne les 2 repos existants:
- `../data` (API data)
- `../dev` (frontend + backend)

Backend inclus dans:
- `../dev/backend` (API métier + worker de sync + persistance)

Et ajoute:
- cluster PostgreSQL primaire/réplique
- monitoring Prometheus + cAdvisor + Grafana
- secrets centralisés dans `infra/secrets`

## Architecture

- `frontend` (public)
  - React/Vite
  - consomme uniquement le `backend`

- `backend` (public + privé)
  - endpoint filtrable pour la carte: `GET /api/v1/readings`
  - worker périodique:
    1. `POST data-api /api/v1/jobs/refresh`
    2. `GET data-api /api/v1/index/history`
    3. upsert PostgreSQL (clé logique `station_code + observed_at`)

- `data-api` (privé uniquement)
  - non exposé
  - accessible uniquement depuis le `backend` sur le réseau privé

- `postgres-primary` + `postgres-replica` (privé uniquement)
  - réplication streaming master/slave
  - backend branché sur `postgres-primary`

- `prometheus`, `cadvisor`, `grafana`
  - supervision conteneurs + métriques backend

## Réseaux

- `public_net`: frontend, backend, monitoring
- `private_net`: backend, data-api, postgres-primary, postgres-replica

`data-api` et les bases ne publient aucun port hôte.

## Secrets centralisés

Les secrets sont tous dans `infra/secrets` (fichiers `.txt`, ignorés Git).

Initialisation:

```bash
cd infra
./scripts/init-secrets.sh
```

## Démarrage

```bash
cd infra
cp .env.example .env
./scripts/init-secrets.sh
docker compose --env-file .env up --build -d
```

## Endpoints utiles

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8787/health`
- Backend data: `http://localhost:8787/api/v1/readings`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Vérifications rapides

```bash
# Trigger manuel d'une sync
curl -X POST http://localhost:8787/api/v1/jobs/sync

# Lire les points pour la carte
curl "http://localhost:8787/api/v1/readings?limit=50"

# Agrégation par ville
curl "http://localhost:8787/api/v1/readings?aggregate_by=city&limit=50"
```

## Filtrage backend

`GET /api/v1/readings` prend en charge:
- `start_date`, `end_date` (YYYY-MM-DD)
- `min_lat`, `max_lat`, `min_lng`, `max_lng`
- `min_index`, `max_index` (0..100)
- `aggregate_by=none|city`
- `limit`

## Haute disponibilité DB

La plateforme fournit une topologie master/slave avec réplication continue:
- écriture sur `postgres-primary`
- standby à chaud sur `postgres-replica`

En cas de panne primaire, la promotion du replica reste une opération d'exploitation (manuelle).
