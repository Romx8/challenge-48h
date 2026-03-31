# Challenge 48h - Data API (usage équipe dev)

API FastAPI qui produit des données consolidées pollution + météo avec un indice prêt à stocker et afficher.

## Ce que les devs reçoivent

Chaque entrée contient au minimum :
- station_code
- latitude
- longitude
- observed_at
- index

Et aussi (utile pour popup/debug/analytique) :
- pollution_score
- meteo_modifier
- risk_level
- pollutants (no2, o3, pm10, pm25, so2, co)
- meteo (temperature_c, humidity_pct, wind_speed_ms, pressure_hpa, precip_mm)

## Contrat API

### 1) Santé
- GET /health

Réponse :
- status = ok
- app = nom de l’application

### 2) Dernière photo disponible
- GET /api/v1/index/latest

Usage : affichage instantané de l’état courant sur la carte.

### 3) Historique
- GET /api/v1/index/history

Paramètres :
- days (optionnel, défaut 10)
- start_date (optionnel, format YYYY-MM-DD)
- end_date (optionnel, format YYYY-MM-DD)

Règle :
- si start_date/end_date sont fournis, ils priment sur days.

Exemples :
- /api/v1/index/history?days=10
- /api/v1/index/history?start_date=2024-04-04&end_date=2024-04-04

### 4) Job de refresh
- POST /api/v1/jobs/refresh

Paramètres :
- days (optionnel)
- start_date (optionnel)
- end_date (optionnel)

Exemples :
- /api/v1/jobs/refresh?days=10
- /api/v1/jobs/refresh?start_date=2024-04-04&end_date=2024-04-04

Réponse :
- status = refreshed
- rows = nombre de lignes consolidées
- generated_at = timestamp UTC

## Flux d’intégration recommandé (backend)

1. CRON appelle POST /api/v1/jobs/refresh toutes les x minutes/heures.
2. Backend appelle GET /api/v1/index/history?days=10 (ou plage de dates).
3. Backend upsert en base avec clé logique : (station_code, observed_at).
4. Front n’appelle que le backend (pas la data API).

## Format d’une entrée (exemple)

{
	"station_code": "FR01011",
	"latitude": 48.979333,
	"longitude": 6.243167,
	"observed_at": "2024-04-04T00:00:00Z",
	"index": 63.4,
	"pollution_score": 58.0,
	"meteo_modifier": 1.09,
	"risk_level": "eleve",
	"pollutants": {
		"no2": 42.1,
		"o3": 71.3,
		"pm10": 27.2,
		"pm25": 18.9,
		"so2": 3.5,
		"co": 0.4
	},
	"meteo": {
		"temperature_c": 11.2,
		"humidity_pct": 84,
		"wind_speed_ms": 1.5,
		"pressure_hpa": 1019,
		"precip_mm": 0
	}
}

## Source de données (runtime)

Mode runtime 100% direct Data.gouv (sans fallback local) :
- Pollution : API objet publique (bucket ineris-prod, flux E2)
- Météo : ressources SYNOP résolues par année via dataset archive-synop-omm

Conséquence :
- si Data.gouv est indisponible, le refresh échoue explicitement (comportement voulu).

## Règles d’indice (résumé)

- pollution_score normalisé/pondéré sur PM2.5, PM10, NO2, O3, SO2, CO
- meteo_modifier basé sur vent/humidité/pression/pluie
- index = min(100, pollution_score * meteo_modifier)
- risk_level : tres_faible, faible, modere, eleve, tres_eleve

## Quickstart dev

### Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker compose up --build
```

### Tests rapides

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/api/v1/index/latest"
curl "http://localhost:8000/api/v1/index/history?days=10"
curl "http://localhost:8000/api/v1/index/history?start_date=2024-04-04&end_date=2024-04-04"
curl -X POST "http://localhost:8000/api/v1/jobs/refresh?days=10"
```

## Exemple CRON backend

```bash
0 */6 * * * curl -X POST "http://data-api:8000/api/v1/jobs/refresh?days=10"
```

## Notes pratiques pour l’équipe dev

- observed_at est en UTC.
- index est borné entre 0 et 100.
- station_distance_km peut être utilisé comme indicateur de qualité de jointure spatiale.
- Pour les filtres frontend (zone, bornes index, dates), appliquez-les côté backend sur votre base stockée.

