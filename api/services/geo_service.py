"""Serialisation des modeles geospatiaux SQLAlchemy en GeoJSON."""
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping


def to_feature(row, properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": mapping(to_shape(row.geometry)),
        "properties": properties,
    }


def to_feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def gares_to_geojson(gares, nb_passages_by_id: dict | None = None) -> dict:
    nb_passages_by_id = nb_passages_by_id or {}
    features = [
        to_feature(
            g,
            {
                "id": g.id,
                "nom": g.nom,
                "ville": g.ville,
                "region_id": g.region_id,
                "source": g.source,
                "osm_id": g.osm_id,
                "osm_nom": g.osm_nom,
                "distance_osm_m": g.distance_osm_m,
                "appariement_osm": g.appariement_osm,
                "nb_passages": nb_passages_by_id.get(g.id, 0),
            },
        )
        for g in gares
    ]
    return to_feature_collection(features)


def lignes_to_geojson(lignes) -> dict:
    features = [
        to_feature(
            l, {"id": l.id, "nom": l.nom, "type_ligne": l.type_ligne, "longueur_km": l.longueur_km}
        )
        for l in lignes
    ]
    return to_feature_collection(features)


def voies_osm_to_geojson(voies) -> dict:
    features = [to_feature(v, {"id": v.id}) for v in voies]
    return to_feature_collection(features)


def regions_to_geojson(regions, couverture_by_id: dict | None = None) -> dict:
    couverture_by_id = couverture_by_id or {}
    features = []
    for r in regions:
        stats = couverture_by_id.get(r.id, {})
        features.append(
            to_feature(
                r,
                {
                    "id": r.id,
                    "nom": r.nom,
                    "superficie_km2": r.superficie_km2,
                    "nb_gares": stats.get("nb_gares", 0),
                    "densite_gares_par_km2": stats.get("densite_gares_par_km2"),
                },
            )
        )
    return to_feature_collection(features)
