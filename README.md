# RailGIS Maroc

## Présentation du projet

**RailGIS Maroc** est une application WebGIS dédiée à la visualisation et à
l'analyse géographique du réseau ferroviaire marocain. Elle rassemble des
données ferroviaires et géographiques, les prépare avec un ETL géospatial, les
expose au moyen d'une API et permet de les explorer sur une carte interactive.

Le projet comprend également un module expérimental de machine learning pour
estimer les retards et la fréquentation. 
## Aperçu de l'application

| Carte générale | Couverture régionale |
|---|---|
| ![Carte générale du réseau](docs/screenshots/carte_generale.png) | ![Carte choroplèthe des gares par région](docs/screenshots/choroplethe.png) |

| Densité de desserte | Horaires d'une gare |
|---|---|
| ![Heatmap de la desserte](docs/screenshots/heatmap.png) | ![Horaires d'une gare](docs/screenshots/horaires_gare.png) |

**Tracé ferroviaire OpenStreetMap**

![Tracé OSM des voies ferrées](docs/screenshots/trace_osm.png)

## Sources de données

- **GTFS ONCF** : arrêts, horaires planifiés, lignes, trajets et tracés associés.
- **OpenStreetMap** : voies ferrées et objets représentant des gares.
- **GADM** : limites administratives régionales du Maroc.
- **Open-Meteo** : historique météorologique horaire utilisé pour enrichir des
  observations fournies pour l'entraînement.
- **Nager.Date** : jours fériés marocains utilisés pour l'enrichissement.



## Fonctionnalités

### 1. Traitement ETL géospatial

Le pipeline ETL Python extrait, transforme et charge des données vectorielles
provenant de plusieurs sources. Il :

- lit et harmonise les fichiers GTFS ;
- transforme les arrêts en points géographiques ;
- assemble les points de tracé GTFS en géométries de lignes ;
- calcule la longueur des lignes dans un système de coordonnées métrique ;
- classe les lignes en LGV, classiques ou navettes à l'aide de règles basées sur
  leurs noms et identifiants ;
- associe spatialement les gares aux régions ;
- rapproche les noms de gares GTFS et OpenStreetMap, puis utilise la proximité
  géographique comme solution de repli ;
- exporte les couches préparées en GeoJSON et les charge dans PostGIS.

Le traitement est de type **batch** : il est lancé sur des fichiers et ne traite
pas un flux d'événements en continu.

### 2. Stockage géospatial

PostgreSQL avec l'extension **PostGIS** conserve les entités et leurs propriétés
géographiques. Les données principales couvrent :

- les gares ;
- les lignes et leurs longueurs ;
- les régions ;
- les tronçons ferroviaires OpenStreetMap ;
- les horaires et jours de service GTFS.

Les couches GeoJSON préparées sont également conservées dans
`data/processed/` pour leur échange et leur visualisation.

### 3. API de données et d'analyse

L'API **FastAPI** donne accès aux données et indicateurs du projet. Elle permet
notamment de :

- récupérer les gares, lignes, voies OSM et régions en GeoJSON ;
- filtrer les gares par région et les lignes par catégorie ;
- consulter les horaires associés à une gare ;
- obtenir un résumé du réseau ;
- calculer le nombre et la densité de gares par région ;
- estimer des indicateurs de fréquentation et de vitesse à partir des données
  GTFS ;
- estimer la durée des trajets directs entre deux gares ;
- vérifier si les modèles de prédiction sont disponibles ;
- demander des estimations de retard et de fréquentation pour des circulations.

Les analyses de fréquentation et de vitesse sont calculées à partir des données
de service disponibles ; elles ne sont pas des comptages réels de passagers ou
des mesures certifiées en exploitation. La recherche d'itinéraire porte sur les
trajets directs et ne calcule pas de correspondances.

### 4. Carte web interactive

L'interface web, construite avec **Leaflet**, permet de :

- visualiser les lignes et les gares sur un fond de carte ;
- distinguer les lignes par couleur selon leur catégorie ;
- filtrer les lignes par type et les gares par région ;
- afficher une choroplèthe du nombre de gares par région ;
- afficher une heatmap de la desserte ;
- superposer le tracé ferroviaire OpenStreetMap ;
- sélectionner une gare pour consulter ses horaires ;
- exporter les couches de gares ou de lignes en GeoJSON ;
- effectuer une prévision expérimentale depuis un formulaire cartographique et
  visualiser le résultat près de la gare concernée.

La carte récupère ses données depuis l'API. Certaines couches géographiques
peuvent aussi utiliser les GeoJSON préparés lorsque l'API n'est pas disponible ;
les horaires et les prédictions nécessitent l'API.

### 5. Prédiction expérimentale et recommandations indicatives

Le module de science des données compare **Random Forest** et **XGBoost** pour
deux cibles :

- le retard estimé en minutes ;
- le nombre de passagers estimé.

Il prépare des variables de calendrier, de ligne et de gare, ainsi que des
variables météorologiques. Le pipeline vérifie les valeurs manquantes et
doublons, signale les valeurs atypiques sans les supprimer automatiquement, et
compare les modèles sur une séparation chronologique entre apprentissage et
évaluation.

Les résultats peuvent être sollicités par l'API et affichés sur la carte. Des
alertes indicatives sont formulées quand les estimations dépassent des seuils
calculés à partir des données d'entraînement.

Le jeu d'entraînement de démonstration est synthétique. Le dépôt ne contient pas
d'historique réel ONCF des retards et du nombre de passagers permettant de
valider ces modèles en conditions opérationnelles.

## Technologies principales

- **Python** : ETL, API et traitement des données.
- **Pandas, GeoPandas et Shapely** : préparation et manipulation des données
  tabulaires et géométriques.
- **PostgreSQL / PostGIS** : stockage et requêtes géospatiales.
- **FastAPI et SQLAlchemy** : services API et accès aux données.
- **Scikit-learn et XGBoost** : entraînement et comparaison des modèles.
- **HTML, CSS, JavaScript et Leaflet** : interface cartographique.
- **Docker Compose** : orchestration de la base, de l'API et du serveur web.

## Structure fonctionnelle

```text
etl/            Acquisition, nettoyage et chargement des données géospatiales
api/            API de données, analyses et prédictions
web/            Carte interactive et formulaire de prédiction
data_science/   Enrichissement, qualité des données, entraînement et prévision
data/processed/ Couches GeoJSON préparées
notebooks/      Exploration des données et statistiques descriptives
docs/screenshots/ Captures de l'application
db/             Initialisation de PostGIS
tests/          Tests du traitement des données et des prédictions
```
