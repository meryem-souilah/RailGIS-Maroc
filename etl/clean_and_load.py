"""Nettoie, harmonise et charge les donnees GTFS + OSM + GADM dans PostGIS.

Etapes :
1. Parse le GTFS ONCF (stops, routes, trips, shapes, stop_times, calendar)
2. Construit les gares (points) et les lignes (lignes brisees) en EPSG:4326
3. Classe chaque ligne par type (LGV / classique / navette)
4. Charge le decoupage regional (GADM) et rattache chaque gare a sa region
5. Charge le trace OSM (voies + gares) et rapproche les gares ONCF/OSM
   (le shapes.txt du GTFS ONCF est genere algorithmiquement, pas un releve
   topographique - le trace OSM sert de reference geometrique precise)
6. Ecrit les tables `regions`, `gares`, `lignes`, `voies_osm`, `horaires` dans PostGIS
7. Exporte des GeoJSON nettoyes dans data/processed/
"""
from __future__ import annotations

import re
import sys
import unicodedata

import geopandas as gpd
import pandas as pd
from config import (
    CRS_MERCHICH,
    CRS_WGS84,
    DATABASE_URL,
    GADM_REGIONS_LAYER,
    GTFS_RAW_DIR,
    OSM_RAW_DIR,
    PROCESSED_DIR,
    REGIONS_RAW_DIR,
)
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from sqlalchemy import create_engine

# Distance max (m) pour rapprocher une gare ONCF (GTFS) d'une station OSM
OSM_MATCH_TOLERANCE_M = 500


def harmonize_name(name: str) -> str:
    """Normalise un nom de gare (espaces, casse) pour rapprocher ONCF/OSM."""
    return " ".join(str(name).strip().split()).title()


def classify_type_ligne(nom: str, route_id: str = "") -> str:
    """Deduit le type de ligne a partir de son nom/route_id (le GTFS ONCF n'a pas
    de champ dedie : Al Boraq = LGV, lignes 'navette' de banlieue, sinon classique)."""
    texte = f"{nom} {route_id}".lower()
    if any(mot in texte for mot in ("boraq", "lgv", "grande vitesse", "high speed", "high_speed")):
        return "LGV"
    if "navette" in texte:
        return "navette"
    return "classique"


def load_gtfs() -> dict[str, pd.DataFrame]:
    tables = {}
    for name in ("stops", "routes", "trips", "shapes", "stop_times", "calendar"):
        path = GTFS_RAW_DIR / f"{name}.txt"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} introuvable - lance d'abord `python download_gtfs.py`."
            )
        tables[name] = pd.read_csv(path, dtype=str)
    return tables


def build_gares(stops: pd.DataFrame) -> gpd.GeoDataFrame:
    stops = stops.copy()
    stops["stop_lat"] = stops["stop_lat"].astype(float)
    stops["stop_lon"] = stops["stop_lon"].astype(float)
    geometry = [Point(lon, lat) for lon, lat in zip(stops["stop_lon"], stops["stop_lat"])]
    gares = gpd.GeoDataFrame(
        {
            "id": stops["stop_id"],
            "nom": stops["stop_name"].map(harmonize_name),
            "ville": stops["stop_name"].map(harmonize_name),
            "source": "ONCF_GTFS",
        },
        geometry=geometry,
        crs=CRS_WGS84,
    )
    return gares.drop_duplicates(subset="id").reset_index(drop=True)


def build_shape_lines(shapes: pd.DataFrame) -> dict[str, LineString]:
    shapes = shapes.copy()
    shapes["shape_pt_sequence"] = shapes["shape_pt_sequence"].astype(int)
    shapes["shape_pt_lat"] = shapes["shape_pt_lat"].astype(float)
    shapes["shape_pt_lon"] = shapes["shape_pt_lon"].astype(float)
    shapes = shapes.sort_values(["shape_id", "shape_pt_sequence"])

    lines: dict[str, LineString] = {}
    for shape_id, group in shapes.groupby("shape_id"):
        coords = list(zip(group["shape_pt_lon"], group["shape_pt_lat"]))
        if len(coords) >= 2:
            lines[shape_id] = LineString(coords)
    return lines


def build_lignes(
    routes: pd.DataFrame, trips: pd.DataFrame, shape_lines: dict[str, LineString]
) -> gpd.GeoDataFrame:
    records = []
    for _, route in routes.iterrows():
        route_id = route["route_id"]
        nom = route.get("route_long_name") or route.get("route_short_name") or route_id
        shape_ids = trips.loc[trips["route_id"] == route_id, "shape_id"].dropna().unique()
        geoms = [shape_lines[sid] for sid in shape_ids if sid in shape_lines]
        if not geoms:
            continue
        geometry = geoms[0] if len(geoms) == 1 else unary_union(geoms)
        records.append(
            {
                "id": route_id,
                "nom": harmonize_name(nom),
                "type_ligne": classify_type_ligne(nom, route_id),
                "geometry": geometry,
            }
        )
    return gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_WGS84)


def build_horaires(
    stop_times: pd.DataFrame, trips: pd.DataFrame, calendar: pd.DataFrame
) -> pd.DataFrame:
    jours_cols = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    calendar = calendar.copy()
    calendar["jours"] = calendar[jours_cols].apply(lambda row: "".join(row), axis=1)

    trips_light = trips[["trip_id", "route_id", "service_id", "direction_id"]].copy()
    trips_light = trips_light.merge(
        calendar[["service_id", "jours"]], on="service_id", how="left"
    )

    horaires = stop_times.merge(trips_light, on="trip_id", how="left")
    horaires = horaires.rename(
        columns={
            "stop_id": "gare_id",
            "route_id": "ligne_id",
            "arrival_time": "heure_arrivee",
            "departure_time": "heure_depart",
            "direction_id": "sens",
        }
    )
    horaires["stop_sequence"] = horaires["stop_sequence"].astype(int)
    return horaires[
        [
            "trip_id",
            "gare_id",
            "ligne_id",
            "heure_arrivee",
            "heure_depart",
            "stop_sequence",
            "sens",
            "jours",
        ]
    ].reset_index(drop=True)


def attach_regions(gares: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame | None]:
    shp_path = REGIONS_RAW_DIR / f"{GADM_REGIONS_LAYER}.shp"
    if not shp_path.exists():
        print(
            f"[warn] {shp_path} introuvable - lance `python download_regions.py` "
            "pour l'analyse de couverture par region. Gares chargees sans region_id."
        )
        gares = gares.copy()
        gares["region_id"] = None
        return gares, None

    regions_raw = gpd.read_file(shp_path).to_crs(CRS_WGS84)
    regions = gpd.GeoDataFrame(
        {
            "id": regions_raw["GID_1"],
            "nom": regions_raw["NAME_1"],
            "superficie_km2": regions_raw.to_crs(CRS_MERCHICH).area / 1e6,
        },
        geometry=regions_raw.geometry,
        crs=CRS_WGS84,
    )

    joined = gpd.sjoin(gares, regions[["id", "geometry"]], how="left", predicate="within")
    joined = joined.rename(columns={"id_left": "id", "id_right": "region_id"})
    joined = joined.drop(columns=[c for c in ("index_right",) if c in joined.columns])
    return joined[["id", "nom", "ville", "source", "region_id", "geometry"]], regions


GARE_COLUMNS = [
    "id",
    "nom",
    "ville",
    "source",
    "region_id",
    "osm_id",
    "osm_nom",
    "distance_osm_m",
    "appariement_osm",
    "geometry",
]


def load_osm() -> tuple[gpd.GeoDataFrame | None, gpd.GeoDataFrame | None]:
    lines_path = OSM_RAW_DIR / "rail_lines.geojson"
    stations_path = OSM_RAW_DIR / "rail_stations.geojson"
    if not lines_path.exists() or not stations_path.exists():
        print(
            f"[warn] Donnees OSM introuvables dans {OSM_RAW_DIR} - lance "
            "`python download_osm.py`. Trace precis et harmonisation ONCF/OSM ignores."
        )
        return None, None
    osm_lines = gpd.read_file(lines_path)
    osm_stations = gpd.read_file(stations_path)
    return osm_lines, osm_stations


def build_voies_osm(osm_lines: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Trace ferroviaire precis (releve OSM), en complement du trace GTFS genere."""
    voies = osm_lines[osm_lines.geometry.type == "LineString"].copy()
    return gpd.GeoDataFrame(
        {"id": voies["osm_id"].astype(str)}, geometry=voies.geometry.values, crs=CRS_WGS84
    )


_BOILERPLATE_TOKENS = {"GARE", "DE", "D", "DU", "LA", "LE", "ONCF", "NOUVELLE"}


def _name_tokens(name) -> frozenset:
    """Jeu de mots-cles normalise (sans accents/casse/ponctuation/mots vides) pour
    comparer un nom de gare GTFS a un nom de station OSM independamment du format
    ('Rabat-Ville' vs 'Gare Rabat Ville', 'Taza' vs 'Nouvelle Gare ONCF de Taza', etc.)."""
    if not name or (isinstance(name, float)):
        return frozenset()
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c)).upper()
    tokens = re.findall(r"[A-Z0-9]+", text)
    return frozenset(t for t in tokens if t not in _BOILERPLATE_TOKENS)


def harmonize_gares_with_osm(
    gares: gpd.GeoDataFrame, osm_stations: gpd.GeoDataFrame | None
) -> gpd.GeoDataFrame:
    """Rapproche chaque gare ONCF (GTFS) de sa station OSM correspondante (harmonisation
    des deux sources, cf. cahier des charges : 'harmonisation des noms de gares ONCF vs OSM').

    Strategie en deux temps : 1) correspondance par nom (les deux jeux de tokens sont
    l'un inclus dans l'autre, ex. {TANGER,AL,BORAQ} <= {TANGER,VILLE,AL,BORAQ}) qui
    resiste aux variations de formulation ; 2) repli sur la station OSM la plus proche
    dans un rayon de tolerance quand aucun nom ne correspond. Le champ `appariement_osm`
    indique la methode retenue, pour permettre une revue manuelle."""
    gares = gares.copy()
    gares["osm_id"] = None
    gares["osm_nom"] = None
    gares["distance_osm_m"] = None
    gares["appariement_osm"] = None

    if osm_stations is None or osm_stations.empty:
        return gares

    stations = osm_stations.copy()
    # certaines stations sont mappees comme batiment/quai (way) plutot que noeud :
    # on prend leur centroide comme position de reference pour l'appariement.
    stations["geometry"] = stations.geometry.apply(
        lambda g: g if g.geom_type == "Point" else g.centroid
    )
    stations["_tokens"] = stations["name"].map(_name_tokens)
    stations = stations[stations["_tokens"].map(bool)]
    stations_m = stations.to_crs(CRS_MERCHICH)
    gares_m = gares.to_crs(CRS_MERCHICH)

    for idx in gares.index:
        gare_tokens = _name_tokens(gares.at[idx, "nom"])
        gare_point = gares_m.at[idx, "geometry"]
        if not gare_tokens:
            continue

        candidats = stations_m[
            stations_m["_tokens"].map(lambda t, gt=gare_tokens: bool(t <= gt or gt <= t))
        ]
        methode = "nom"
        if candidats.empty:
            distances = stations_m.geometry.distance(gare_point)
            if distances.empty or distances.min() > OSM_MATCH_TOLERANCE_M:
                continue
            candidats = stations_m.loc[[distances.idxmin()]]
            methode = "proximite"

        distances = candidats.geometry.distance(gare_point)
        best = candidats.loc[distances.idxmin()]

        gares.at[idx, "osm_id"] = str(best["osm_id"])
        gares.at[idx, "osm_nom"] = best["name"]
        gares.at[idx, "distance_osm_m"] = round(float(distances.min()), 1)
        gares.at[idx, "appariement_osm"] = methode

    # sans ce cast, la colonne reste dtype `object` (None + float melanges) et
    # geopandas.to_postgis() la charge en TEXT au lieu de DOUBLE PRECISION.
    gares["distance_osm_m"] = pd.to_numeric(gares["distance_osm_m"], errors="coerce")

    nb_matched = gares["osm_id"].notna().sum()
    nb_nom = (gares["appariement_osm"] == "nom").sum()
    print(
        f"Harmonisation ONCF/OSM : {nb_matched}/{len(gares)} gares rapprochees "
        f"({nb_nom} par nom, {nb_matched - nb_nom} par proximite <{OSM_MATCH_TOLERANCE_M} m)"
    )
    return gares


def export_geojson(gares, lignes, regions, voies_osm) -> None:
    gares.to_file(PROCESSED_DIR / "gares.geojson", driver="GeoJSON")
    lignes.to_file(PROCESSED_DIR / "lignes.geojson", driver="GeoJSON")
    if regions is not None:
        regions.to_file(PROCESSED_DIR / "regions.geojson", driver="GeoJSON")
    if voies_osm is not None:
        voies_osm.to_file(PROCESSED_DIR / "voies_osm.geojson", driver="GeoJSON")
    print(f"GeoJSON nettoyes exportes dans {PROCESSED_DIR}")


def load_to_postgis(gares, lignes, horaires, regions, voies_osm) -> None:
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect():
            pass
    except Exception as exc:  # noqa: BLE001 - on veut juste degrader proprement
        print(f"[warn] PostGIS injoignable ({exc}) - etape de chargement DB ignoree.")
        return

    if regions is not None:
        regions.to_postgis("regions", engine, if_exists="replace", index=False)
    gares.to_postgis("gares", engine, if_exists="replace", index=False)
    lignes.to_postgis("lignes", engine, if_exists="replace", index=False)
    if voies_osm is not None:
        voies_osm.to_postgis("voies_osm", engine, if_exists="replace", index=False)
    horaires.to_sql("horaires", engine, if_exists="replace", index=True, index_label="id")
    print("Tables `regions`, `gares`, `lignes`, `voies_osm`, `horaires` chargees dans PostGIS.")


def main() -> None:
    print("Chargement du GTFS ONCF...")
    gtfs = load_gtfs()

    gares = build_gares(gtfs["stops"])
    shape_lines = build_shape_lines(gtfs["shapes"])
    lignes = build_lignes(gtfs["routes"], gtfs["trips"], shape_lines)
    lignes["longueur_km"] = (lignes.to_crs(CRS_MERCHICH).length / 1000).round(1)
    horaires = build_horaires(gtfs["stop_times"], gtfs["trips"], gtfs["calendar"])

    gares, regions = attach_regions(gares)

    osm_lines, osm_stations = load_osm()
    gares = harmonize_gares_with_osm(gares, osm_stations)
    gares = gares[GARE_COLUMNS]
    voies_osm = build_voies_osm(osm_lines) if osm_lines is not None else None

    export_geojson(gares, lignes, regions, voies_osm)
    load_to_postgis(gares, lignes, horaires, regions, voies_osm)

    print(
        f"Termine : {len(gares)} gares, {len(lignes)} lignes, "
        f"{len(horaires)} horaires"
        + (f", {len(regions)} regions" if regions is not None else "")
        + (f", {len(voies_osm)} troncons OSM" if voies_osm is not None else "")
    )


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
