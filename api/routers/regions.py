from fastapi import APIRouter, Depends
from models.schema import Region
from services.analyse_service import couverture_par_region
from services.db import get_db
from services.geo_service import regions_to_geojson
from sqlalchemy.orm import Session

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("")
def get_regions(db: Session = Depends(get_db)):
    couverture_by_id = {r["region_id"]: r for r in couverture_par_region(db)}
    return regions_to_geojson(db.query(Region).all(), couverture_by_id)
