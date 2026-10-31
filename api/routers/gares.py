from fastapi import APIRouter, Depends, HTTPException, Query
from models.schema import Gare, Horaire
from services.db import get_db
from services.geo_service import gares_to_geojson
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/gares", tags=["gares"])


@router.get("")
def get_gares(
    region_id: str | None = Query(None, description="Filtrer par identifiant de region"),
    db: Session = Depends(get_db),
):
    query = db.query(Gare)
    if region_id:
        query = query.filter(Gare.region_id == region_id)

    nb_passages_by_id = dict(
        db.query(Horaire.gare_id, func.count(Horaire.id)).group_by(Horaire.gare_id).all()
    )
    return gares_to_geojson(query.all(), nb_passages_by_id)


@router.get("/{gare_id}/horaires")
def get_horaires_gare(gare_id: str, db: Session = Depends(get_db)):
    gare = db.query(Gare).filter(Gare.id == gare_id).first()
    if gare is None:
        raise HTTPException(status_code=404, detail="Gare introuvable")

    horaires = (
        db.query(Horaire)
        .filter(Horaire.gare_id == gare_id)
        .order_by(Horaire.heure_depart)
        .all()
    )
    return {
        "gare_id": gare.id,
        "gare_nom": gare.nom,
        "nb_passages": len(horaires),
        "horaires": [
            {
                "trip_id": h.trip_id,
                "ligne_id": h.ligne_id,
                "heure_arrivee": h.heure_arrivee,
                "heure_depart": h.heure_depart,
                "sens": h.sens,
                "jours": h.jours,
            }
            for h in horaires
        ],
    }
