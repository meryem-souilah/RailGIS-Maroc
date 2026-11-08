# RailGIS Maroc

Analyse et cartographie web du réseau ferroviaire marocain (ONCF) : ETL géospatial
(GTFS + OSM + GADM), API FastAPI, carte interactive Leaflet (choroplèthe, heatmap,
tracé OSM précis), analyses spatiales et pipeline expérimental de prédiction
(retards et fréquentation).

![type de ligne](https://img.shields.io/badge/stack-Python%20%2B%20PostGIS%20%2B%20FastAPI%20%2B%20Leaflet-2980b9)

## Aperçu

| Carte generale | Couverture regionale (choroplèthe) |
|---|---|
| ![Carte generale](docs/screenshots/carte_generale.png) | ![Choroplèthe](docs/screenshots/choroplethe.png) |

| Densite de desserte (heatmap) | Horaires d'une gare |
|---|---|
| ![Heatmap](docs/screenshots/heatmap.png) | ![Horaires](docs/screenshots/horaires_gare.png) |

Le trace precis OpenStreetMap (superposable au trace GTFS, genere algorithmiquement) :

![Trace OSM](docs/screenshots/trace_osm.png)

## Architecture

```
RailGIS_Maroc/
├── etl/            # Téléchargement + nettoyage + harmonisation ONCF/OSM + chargement PostGIS
├── api/            # API FastAPI (GeoJSON, horaires, indicateurs)
├── web/            # Carte Leaflet statique (HTML/CSS/JS)
├── data/
│   ├── raw/        # Téléchargé, non versionné (.gitignore)
│   └── processed/  # GeoJSON nettoyés, exportés par l'ETL
├── notebooks/      # Analyse exploratoire (Jupyter)
├── data_science/   # Enrichissement météo/calendrier, modèles et recommandations
├── docs/screenshots/ # Captures d'ecran (README)
├── db/init.sql     # Activation de l'extension PostGIS
└── docker-compose.yml
```

## Sources de données

| Source | Contenu | Licence |
|---|---|---|
| [GTFS ONCF](https://github.com/newsbubbles/rail_maroc_oncf) | Lignes, arrêts, horaires | ODbL |
| [OpenStreetMap](https://www.openstreetmap.org) (Overpass API) | Tracé des voies, gares | ODbL — © OpenStreetMap contributors |
| [GADM v4.1](https://gadm.org) | Découpage régional du Maroc | Usage académique / non-commercial |
| [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api) | Météo horaire historique par coordonnées | Conditions d'utilisation Open-Meteo |
| [Nager.Date](https://date.nager.at/) | Jours fériés publics par pays et année | API publique |

## Démarrage rapide

Prérequis : Docker Desktop, Python 3.11+.

```bash
# 1. Copier la config d'environnement
cp .env.example .env

# 2. Lancer PostGIS
docker compose up -d db

# 3. Installer les dépendances ETL et exécuter le pipeline
cd etl
pip install -r requirements.txt
python download_gtfs.py       # ~30 ko, gares/lignes/horaires ONCF
python download_regions.py    # ~3 Mo, découpage régional GADM
python download_osm.py        # tracé + gares OSM (Overpass API) ; sans ce fichier,
                               # clean_and_load.py se degrade sans harmonisation ONCF/OSM
python clean_and_load.py      # nettoie, harmonise, charge dans PostGIS + GeoJSON

# 4. Lancer l'API + la carte
cd ..
docker compose up -d --build api web
```

- API : http://localhost:8000 (documentation interactive sur `/docs`)
- Carte : http://localhost:8090

> Le port hôte 5432 est parfois déjà pris par une instance PostgreSQL locale :
> le conteneur `db` expose alors PostGIS sur **5433** (`POSTGRES_HOST_PORT` dans `.env`
> pour changer). Idem pour le port web, exposé par défaut sur **8090**
> (`WEB_PORT`). Les conteneurs communiquent entre eux via le réseau interne Docker
> (`db:5432`), ces ports hôtes ne concernent que l'accès depuis ta machine.

Sans Docker pour l'API, tu peux aussi lancer directement :

Depuis `api/`, assure-toi que le dossier racine du dépôt est dans
`PYTHONPATH` (par exemple `export PYTHONPATH=..` sous bash ou
`$env:PYTHONPATH=".."` sous PowerShell), car l'API importe le paquet
`data_science/`.

```bash
cd api
pip install -r requirements.txt
DATABASE_URL=postgresql://railgis:railgis@localhost:5433/railgis_maroc uvicorn main:app --reload
```

## Endpoints API

| Endpoint | Description |
|---|---|
| `GET /lignes` | Lignes du réseau (GeoJSON, avec `longueur_km`), filtrable par `?type_ligne=LGV\|classique\|navette` |
| `GET /lignes/osm` | Trace ferroviaire precis releve par OpenStreetMap (GeoJSON) |
| `GET /gares` | Gares du réseau (GeoJSON : région, correspondance OSM, nb de passages/jour), filtrable par `?region_id=...` |
| `GET /gares/{id}/horaires` | Horaires de passage à une gare |
| `GET /regions` | Découpage régional (GeoJSON) avec nombre de gares par région |
| `GET /analyse/resume` | Totaux réseau (gares, lignes, km, régions) |
| `GET /analyse/couverture` | Nombre de gares et densité par région |
| `GET /analyse/frequentation` | Nombre de trains/jour par ligne |
| `GET /analyse/vitesse` | Vitesse commerciale moyenne (km/h) par type de ligne (LGV vs classique) |
| `GET /analyse/trajet?origine=...&destination=...` | Temps de trajet estimé entre deux gares (recherche par sous-chaîne du nom) |
| `GET /predictions/status` | Vérifie la disponibilité et la provenance des modèles de prédiction |
| `POST /predictions` | Prédit le retard et la fréquentation de 1 à 200 circulations |

> Les noms de gares suivent le GTFS ONCF (ex. **Casa-Voyageurs**, pas "Casablanca" ;
> **Tanger-Ville**, pas "Tanger centre"). `GET /gares` liste les noms exacts.

## Harmonisation ONCF / OpenStreetMap

`etl/clean_and_load.py` rapproche chaque gare du GTFS ONCF de son équivalent
OpenStreetMap : comparaison par jeux de mots-clés normalisés (insensible aux
accents, à la casse et aux tournures type "Gare de X" / "X-Ville" / "Nouvelle
Gare ONCF de X"), avec repli sur la station OSM la plus proche si aucun nom ne
correspond. Résultat sur le jeu de données actuel : **31 gares sur 33** rapprochées
(dont 2 non trouvées dans OSM — Béni Mellal, Casa-Oasis — documenté dans les
propriétés `osm_id` / `appariement_osm` de chaque gare pour revue manuelle).

## Carte interactive : couches d'analyse

En plus des lignes/gares, la sidebar propose trois couches optionnelles :

- **Couverture régionale** : choroplèthe des régions colorée par nombre de gares
  (`GET /regions`).
- **Densité de desserte** : heatmap pondérée par le nombre de passages/jour à
  chaque gare.
- **Tracé précis (OSM)** : trace ferroviaire tel que relevé sur OpenStreetMap, en
  complément du tracé GTFS généré algorithmiquement.

## Notebook d'analyse

`notebooks/analyse_exploratoire.ipynb` charge les GeoJSON nettoyés, calcule la
longueur totale du réseau, affiche une carte statique et la répartition des gares
par région.

## Prédiction expérimentale : retards et fréquentation

Le dossier `data_science/` ajoute un pipeline qui prépare des variables météo et
calendrier, contrôle les valeurs manquantes et doublons, signale les valeurs
atypiques sans les supprimer automatiquement, compare **Random Forest** et
**XGBoost**, puis produit des prévisions et des alertes explicables. Il n'existe
pas, dans les sources de données actuelles
du dépôt, d'historique ONCF public contenant les retards réels et le nombre de
passagers par train. Le GTFS fournit les horaires planifiés, pas ces résultats
observés. **Le jeu de démonstration est donc synthétique ; ses scores et ses
prévisions ne décrivent pas la performance réelle de l'ONCF et ne doivent pas
guider l'exploitation.**

Le pipeline est aussi branché à l'API FastAPI et à la carte Leaflet. Le panneau
**Prévision expérimentale** de la carte permet de choisir une gare, une ligne,
une date/heure planifiée, la météo et le statut de jour férié. Après envoi à
`POST /predictions`, la carte affiche le retard et le nombre de passagers estimés,
les alertes, et un marqueur sur la gare. `GET /predictions/status` indique si
les fichiers modèles sont disponibles. Le panneau ne s'active que si les deux
modèles et le rapport d'entraînement sont présents dans `MODEL_DIR`.

Pour une démonstration reproductible (Python 3.11 recommandé), générer les données
et entraîner les modèles avant de démarrer l'API :

```bash
pip install -r data_science/requirements.txt
python -m data_science.make_demo_data
python -m data_science.train --input data/demo/operations_synthetiques.csv
docker compose up -d --build api web
```

Le générateur réutilise les identifiants et coordonnées géographiques du jeu
cartographique, mais invente les dates, retards, passagers et météo. Chaque ligne
porte `is_synthetic=true` ; cette provenance est incluse dans le rapport et les
résultats. Les modèles et métriques sont écrits dans `models/trained/` (ignoré
par Git), et les recommandations dans
`data/processed/previsions_et_recommandations.csv`.
Docker monte `models/trained/` en lecture seule dans le conteneur API ; il faut
donc entraîner les modèles sur l'hôte avant `docker compose up`. Si on les
réentraîne, redémarrer l'API pour qu'elle lise les nouveaux artefacts :
`docker compose restart api`.

Pour entraîner les modèles sur des données d'exploitation, fournir un CSV avec
une ligne par observation de train en gare et les colonnes :

| Colonne | Description |
|---|---|
| `scheduled_datetime`, `actual_datetime` | Horodatages planifié et réel, au fuseau local du Maroc |
| `line_id`, `station_id` | Identifiants de ligne et de gare |
| `passenger_count` | Nombre de passagers observé, non fourni par le GTFS |
| `latitude`, `longitude` | Coordonnées de gare requises pour l'enrichissement météo |

Les résultats (`actual_datetime`, `passenger_count`) ne sont pas envoyés aux
services météo. Enrichir les observations puis entraîner les modèles :

```bash
python -m data_science.enrich_external --input data/raw/operations.csv
python -m data_science.train --input data/processed/operations_enrichies.csv
```

L'enrichissement demande les conditions historiques horaires à Open-Meteo et les
jours fériés marocains à Nager.Date ; une connexion Internet est nécessaire. Les
requêtes transmettent les coordonnées de gare et les dates nécessaires à ces
services. Le script s'arrête explicitement si une source ne répond pas ou si une
heure météo manque. Le rapport compare les modèles sur les 20 % les plus récents
des observations, après entraînement sur les 80 % précédentes, et retient celui
ayant la plus faible erreur absolue moyenne. Les recommandations sont des règles
indicatives fondées sur les seuils du jeu d'entraînement (P90) ; elles ne
remplacent ni une validation métier ni les contraintes réelles de capacité.
Le rapport inclut aussi le nombre de doublons et de lignes écartées, les mois
couverts et les valeurs atypiques détectées ; ces dernières restent dans le
jeu d'entraînement afin de ne pas effacer automatiquement des retards rares mais
réels.

Après avoir entraîné un modèle, le CSV de prévision doit contenir les variables
de planification, d'identification, météo et calendrier requises (`scheduled_datetime`,
`line_id`, `station_id`, `temperature_c`, `precipitation_mm`, `wind_speed_kmh`,
`is_holiday`) :

```bash
python -m data_science.predict --input data/processed/prochaines_circulations.csv
```

Le même modèle peut être utilisé depuis la carte ou par requête HTTP. Exemple de
corps pour `POST /predictions` :

```json
{
  "observations": [{
    "scheduled_datetime": "2025-01-01T08:00:00",
    "line_id": "AL_BORAQ_TNG_CASA",
    "station_id": "TANGER_VILLE",
    "temperature_c": 20,
    "precipitation_mm": 0,
    "wind_speed_kmh": 10,
    "is_holiday": false
  }]
}
```

Le lot est limité à 200 observations par requête. Le statut `GET
/predictions/status` retourne `available: false` tant que les artefacts ne sont
pas disponibles ; le point de terminaison de prédiction répond alors avec HTTP
503. Les entrées invalides sont refusées avec HTTP 422. L'API charge les modèles
depuis `MODEL_DIR` (par défaut `models/trained/` à la racine du dépôt). Ces
artefacts sérialisés doivent provenir de l'entraînement local de confiance du
projet ; ne chargez jamais de modèles joblib provenant d'une source inconnue.

Les retards et passagers réels demeurent indispensables à un entraînement
opérationnel. Aucun historique de ce type n'est téléchargé ni inventé sous
l'étiquette de données réelles par le projet.

## Tests et lint

```bash
pip install -r api/requirements.txt -r etl/requirements.txt -r data_science/requirements.txt ruff pytest
ruff check api etl data_science
pytest
```


