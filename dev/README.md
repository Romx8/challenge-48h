# Air Map - Frontend + Backend

Ce repo contient:
- un frontend React/Vite,
- un backend FastAPI dans `backend/`,
- des assets/config pour le runtime Docker local.

## Technologies

- Docker / Docker Compose
- Frontend: React + Vite
- UI/Anim: Leaflet (CDN), GSAP, Lenis
- Base de données: PostgreSQL 16

## Prérequis

Option recommandée:
- Docker Desktop (ou Docker CLI + Docker Compose + runtime Docker)

Option locale (non obligatoire):
- Node.js 20+
- npm 10+

## Démarrage sur environnement vierge

1. Copier les variables:
```bash
cp .env.example .env
```

2. Lancer la plateforme:
```bash
docker compose up --build -d
```

3. Accéder au frontend:
- http://localhost:5173

4. Vérifier PostgreSQL:
```bash
psql "postgresql://postgres:postgres@localhost:5432/air_map" -c "SELECT 1;"
```

## Variables d'environnement

Voir `.env.example`:
- frontend: `FRONTEND_PORT`, `VITE_APP_NAME`, `FRONTEND_CONTAINER_NAME`
- postgres: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST_PORT`, `POSTGRES_CONTAINER_NAME`
- future API/backend: `DATABASE_URL`

## Architecture Docker locale

- `frontend`:
  - exposé sur `FRONTEND_PORT` (par défaut `5173`)
- `postgres`:
  - exposé localement sur `127.0.0.1:POSTGRES_HOST_PORT` (par défaut `5432`)
  - volume persistant `postgres_data`
- réseaux:
  - `frontend_net`
  - `backend_net`

Note: la DB est isolée sur son réseau interne Docker; en local elle est aussi accessible en loopback pour debug (`127.0.0.1`).

## État actuel de la data

- Le frontend appelle le backend pour charger les points de la carte.
- Le backend interroge l’API data, persiste les mesures en PostgreSQL, puis expose les filtres.

## Commandes utiles

Arrêter:
```bash
docker compose stop
```

Relancer:
```bash
docker compose up -d
```

Stop + suppression conteneurs:
```bash
docker compose down
```

Suppression conteneurs + volume DB:
```bash
docker compose down -v
```
