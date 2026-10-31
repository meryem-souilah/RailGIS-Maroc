from fastapi import APIRouter, Depends, Query
from services.analyse_service import (
    couverture_par_region,
    estimer_trajet,
    frequentation_par_ligne,
    resume_reseau,
    vitesse_par_type_ligne,
)
from services.db import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/analyse", tags=["analyse"])


@router.get("/resume")
def get_resume(db: Session = Depends(get_db)):
    return resume_reseau(db)


@router.get("/couverture")
def get_couverture(db: Session = Depends(get_db)):
    return {"indicateur": "couverture_par_region", "resultats": couverture_par_region(db)}


@router.get("/frequentation")
def get_frequentation(db: Session = Depends(get_db)):
    return {"indicateur": "frequentation_par_ligne", "resultats": frequentation_par_ligne(db)}


@router.get("/vitesse")
def get_vitesse(db: Session = Depends(get_db)):
    return {"indicateur": "vitesse_par_type_ligne", "resultats": vitesse_par_type_ligne(db)}


@router.get("/trajet")
def get_trajet(
    origine: str = Query(..., description="Nom (ou partie du nom) de la gare de depart"),
    destination: str = Query(..., description="Nom (ou partie du nom) de la gare d'arrivee"),
    db: Session = Depends(get_db),
):
    return estimer_trajet(db, origine, destination)
