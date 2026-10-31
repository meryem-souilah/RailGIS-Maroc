"""Indicateurs d'analyse spatiale : couverture par region, estimation de trajet."""
from collections import defaultdict

from models.schema import Gare, Ligne, Region
from sqlalchemy import func, text
from sqlalchemy.orm import Session


def parse_gtfs_time(value: str) -> int:
    """Convertit un horaire GTFS (peut depasser 24:00:00) en secondes depuis minuit."""
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def couverture_par_region(db: Session) -> list[dict]:
    rows = (
        db.query(
            Region.id,
            Region.nom,
            Region.superficie_km2,
            func.count(Gare.id).label("nb_gares"),
        )
        .outerjoin(Gare, Gare.region_id == Region.id)
        .group_by(Region.id, Region.nom, Region.superficie_km2)
        .all()
    )
    result = []
    for region_id, nom, superficie, nb_gares in rows:
        densite = (nb_gares / superficie) if superficie else None
        result.append(
            {
                "region_id": region_id,
                "region": nom,
                "superficie_km2": round(superficie, 1) if superficie else None,
                "nb_gares": nb_gares,
                "densite_gares_par_km2": round(densite, 5) if densite else None,
            }
        )
    return sorted(result, key=lambda r: r["nb_gares"], reverse=True)


def estimer_trajet(db: Session, origine: str, destination: str) -> dict:
    query = text(
        """
        SELECT
            ho.trip_id,
            ho.heure_depart AS depart,
            hd.heure_arrivee AS arrivee,
            go.nom AS gare_origine,
            gd.nom AS gare_destination
        FROM horaires ho
        JOIN horaires hd
            ON ho.trip_id = hd.trip_id
            AND ho.stop_sequence < hd.stop_sequence
        JOIN gares go ON go.id = ho.gare_id
        JOIN gares gd ON gd.id = hd.gare_id
        WHERE go.nom ILIKE :origine AND gd.nom ILIKE :destination
        ORDER BY ho.heure_depart
        """
    )
    rows = db.execute(
        query, {"origine": f"%{origine}%", "destination": f"%{destination}%"}
    ).fetchall()

    if not rows:
        return {
            "origine": origine,
            "destination": destination,
            "trouve": False,
            "message": "Aucun trajet direct trouve pour ces deux gares.",
        }

    trajets = []
    for row in rows:
        try:
            duree_min = (parse_gtfs_time(row.arrivee) - parse_gtfs_time(row.depart)) / 60
        except (ValueError, AttributeError):
            continue
        if duree_min > 0:
            trajets.append(duree_min)

    if not trajets:
        return {
            "origine": origine,
            "destination": destination,
            "trouve": False,
            "message": "Trajets trouves mais horaires invalides.",
        }

    return {
        "origine": rows[0].gare_origine,
        "destination": rows[0].gare_destination,
        "trouve": True,
        "nb_trains_directs": len(trajets),
        "duree_min_minutes": round(min(trajets)),
        "duree_moyenne_minutes": round(sum(trajets) / len(trajets)),
        "duree_max_minutes": round(max(trajets)),
    }


def resume_reseau(db: Session) -> dict:
    return {
        "nb_gares": db.query(Gare).count(),
        "nb_lignes": db.query(Ligne).count(),
        "longueur_totale_km": round(db.query(func.sum(Ligne.longueur_km)).scalar() or 0, 1),
        "nb_regions": db.query(Region).count(),
    }


def frequentation_par_ligne(db: Session) -> list[dict]:
    """Nombre de trains/jour (base sur les services actifs le lundi) par ligne."""
    query = text(
        """
        SELECT h.ligne_id, l.nom, l.type_ligne,
               COUNT(DISTINCT h.trip_id) FILTER (WHERE LEFT(h.jours, 1) = '1') AS nb_trains_jour
        FROM horaires h
        JOIN lignes l ON l.id = h.ligne_id
        GROUP BY h.ligne_id, l.nom, l.type_ligne
        ORDER BY nb_trains_jour DESC
        """
    )
    rows = db.execute(query).fetchall()
    return [
        {
            "ligne_id": r.ligne_id,
            "nom": r.nom,
            "type_ligne": r.type_ligne,
            "nb_trains_jour": r.nb_trains_jour,
        }
        for r in rows
    ]


def vitesse_par_type_ligne(db: Session) -> list[dict]:
    """Vitesse commerciale moyenne (km/h) par type de ligne, a partir de la duree
    reelle des trajets (horaires) et de la longueur du trace (lignes.longueur_km)."""
    query = text(
        """
        SELECT h.trip_id, l.type_ligne, l.longueur_km,
               MIN(h.heure_depart) AS depart, MAX(h.heure_arrivee) AS arrivee
        FROM horaires h
        JOIN lignes l ON l.id = h.ligne_id
        GROUP BY h.trip_id, l.type_ligne, l.longueur_km
        """
    )
    rows = db.execute(query).fetchall()

    vitesses_par_type = defaultdict(list)
    for row in rows:
        if not row.longueur_km:
            continue
        try:
            duree_h = (parse_gtfs_time(row.arrivee) - parse_gtfs_time(row.depart)) / 3600
        except (ValueError, AttributeError):
            continue
        if duree_h > 0:
            vitesses_par_type[row.type_ligne].append(row.longueur_km / duree_h)

    result = []
    for type_ligne, vitesses in vitesses_par_type.items():
        moyenne_kmh = sum(vitesses) / len(vitesses)
        result.append(
            {
                "type_ligne": type_ligne,
                "nb_trajets_analyses": len(vitesses),
                "vitesse_moyenne_kmh": round(moyenne_kmh, 1),
                "temps_moyen_min_par_100km": round(100 / moyenne_kmh * 60, 1),
            }
        )
    return sorted(result, key=lambda r: r["vitesse_moyenne_kmh"], reverse=True)
