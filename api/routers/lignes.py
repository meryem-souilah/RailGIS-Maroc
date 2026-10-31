from fastapi import APIRouter, Depends, Query
from models.schema import Ligne, VoieOsm
from services.db import get_db
from services.geo_service import lignes_to_geojson, voies_osm_to_geojson
from sqlalchemy.orm import Session

router = APIRouter(prefix="/lignes", tags=["lignes"])


@router.get("")
def get_lignes(
    type_ligne: str | None = Query(None, description="Filtrer par type : LGV, classique, navette"),
    db: Session = Depends(get_db),
):
    query = db.query(Ligne)
    if type_ligne:
        query = query.filter(Ligne.type_ligne == type_ligne)
    return lignes_to_geojson(query.all())


@router.get("/osm")
def get_lignes_osm(db: Session = Depends(get_db)):
    """Trace ferroviaire precis releve par OpenStreetMap (complement du trace
    GTFS, genere algorithmiquement par la source ONCF)."""
    return voies_osm_to_geojson(db.query(VoieOsm).all())
