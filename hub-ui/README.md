# Hub UI (Streamlit)

Interface centralisée légère pour piloter les services `dev`, `data` et `infra`.

## Fonctions

- Dashboard global (état des containers)
- Visualisation interactive des flux inter-services (incluant data.gouv.fr et GeoD'Air)
- Pilotage Docker (démarrer/arrêter/redémarrer la stack hors `hub-ui`)
- Détail service par service (statut, health, image, ports, actions start/stop/restart)
- Logs Docker par service avec mode temps réel
- Navigation horizontale en haut de page
- Accès à:
  - Dev app
  - Data API (Swagger / ReDoc)
  - Prometheus (via API interne + liens directs)
  - Grafana
  - Blackbox

## Note Prometheus

Prometheus bloque l'affichage en iframe (header `X-Frame-Options`), donc l'onglet Monitoring:
- affiche les données Prometheus directement via l'API (`/api/v1/query`, `/api/v1/targets`)
- expose des liens directs vers l'UI Prometheus (`/graph`, `/targets`)

## Ajouter un nouveau service plus tard

1. Ajouter le service dans `docker-compose.yml` (racine)
2. Exposer son URL publique (host port)
3. Ajouter l'entrée dans `SERVICES` dans `app.py`:
   - `label`
   - `url`
4. Si nécessaire, ajouter une section dédiée (nouvel onglet/page)

## Lancer localement (hors compose)

```bash
cd hub-ui
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
