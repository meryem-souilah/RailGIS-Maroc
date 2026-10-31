# RailGIS Maroc

Analyse et cartographie web du réseau ferroviaire marocain (ONCF) : ETL geospatial
(GTFS + OSM + GADM), API FastAPI, carte interactive Leaflet (choroplèthe, heatmap,
tracé OSM precis) et analyses spatiales (couverture, fréquentation, vitesse, trajet).

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

## Tests et lint

```bash
pip install -r api/requirements.txt -r etl/requirements.txt ruff pytest
ruff check api etl
pytest
```

## Limites connues / pistes d'amélioration

- Le GTFS `rail_maroc_oncf` couvre un sous-ensemble du réseau (33 gares, 3 lignes,
  888 km) ; son `shapes.txt` est généré algorithmiquement par la source (script
  `generate_shapes.py` du dépôt amont), pas un relevé topographique — d'où l'intérêt
  du tracé OSM fourni en couche complémentaire (`GET /lignes/osm`).
- La classification LGV / classique / navette est une heuristique par mots-clés sur
  le nom et l'identifiant de ligne (le GTFS ne porte pas de champ dédié).
- `analyse/trajet` renvoie les trajets **directs** uniquement (pas de correspondances).
- 2 gares sur 33 n'ont pas d'équivalent trouvé dans OSM (cf. section harmonisation).
- Bonus GeoAI possibles (cf. cahier des charges) : clustering des gares
  sous-desservies (DBSCAN), prédiction de temps de trajet par régression.
