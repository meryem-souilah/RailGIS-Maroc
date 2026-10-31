"""Telecharge le trace ferroviaire et les gares depuis OpenStreetMap (Overpass API).

Recupere les voies (railway=rail) et les gares (railway=station) dans
l'emprise du Maroc, et ecrit deux GeoJSON bruts.
Source : OpenStreetMap contributors (ODbL) - https://overpass-api.de
"""
import json
import sys

import requests
from config import MOROCCO_BBOX, OSM_RAW_DIR, OVERPASS_URL

QUERY_TEMPLATE = """
[out:json][timeout:180];
(
  way["railway"="{railway_tag}"]({bbox});
  node["railway"="{railway_tag}"]({bbox});
);
out body geom;
"""


HEADERS = {
    # overpass-api.de renvoie 406 sans User-Agent explicite (bloque le UA par defaut de `requests`).
    "User-Agent": "RailGIS-Maroc/1.0 (projet PFE WebGIS, etl/download_osm.py)",
    "Accept": "application/json",
}


def fetch_overpass(railway_tag: str, retries: int = 3) -> dict:
    bbox = ",".join(str(v) for v in MOROCCO_BBOX)
    query = QUERY_TEMPLATE.format(railway_tag=railway_tag, bbox=bbox)
    print(f"Requete Overpass pour railway={railway_tag} ...")
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=200
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_exc = exc
            print(f"  tentative {attempt}/{retries} echouee ({exc}), nouvel essai...")
    raise last_exc


def osm_elements_to_geojson(osm_json: dict) -> dict:
    """Convertit une reponse Overpass (out geom) en FeatureCollection GeoJSON."""
    features = []
    for element in osm_json.get("elements", []):
        tags = element.get("tags", {})
        if element["type"] == "node":
            geometry = {"type": "Point", "coordinates": [element["lon"], element["lat"]]}
        elif element["type"] == "way" and "geometry" in element:
            coords = [[pt["lon"], pt["lat"]] for pt in element["geometry"]]
            geometry = {"type": "LineString", "coordinates": coords}
        else:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"osm_id": element["id"], **tags},
                "geometry": geometry,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def download_osm() -> None:
    rails = fetch_overpass("rail")
    stations = fetch_overpass("station")

    rails_geojson = osm_elements_to_geojson(rails)
    stations_geojson = osm_elements_to_geojson(stations)

    (OSM_RAW_DIR / "rail_lines.geojson").write_text(
        json.dumps(rails_geojson, ensure_ascii=False), encoding="utf-8"
    )
    (OSM_RAW_DIR / "rail_stations.geojson").write_text(
        json.dumps(stations_geojson, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"OSM telecharge : {len(rails_geojson['features'])} troncons de voie, "
        f"{len(stations_geojson['features'])} gares -> {OSM_RAW_DIR}"
    )


if __name__ == "__main__":
    try:
        download_osm()
    except requests.RequestException as exc:
        print(f"Erreur de telechargement OSM : {exc}", file=sys.stderr)
        sys.exit(1)
