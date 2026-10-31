"""Shared configuration for the RailGIS Maroc ETL pipeline."""
import os
from pathlib import Path

ETL_DIR = Path(__file__).resolve().parent
ROOT_DIR = ETL_DIR.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

GTFS_RAW_DIR = RAW_DIR / "gtfs"
OSM_RAW_DIR = RAW_DIR / "osm"
REGIONS_RAW_DIR = RAW_DIR / "regions"

# Source: github.com/newsbubbles/rail_maroc_oncf (GTFS ONCF, licence ODbL)
GTFS_BASE_URL = "https://raw.githubusercontent.com/newsbubbles/rail_maroc_oncf/main/gtfs"
GTFS_FILES = [
    "agency.txt",
    "calendar.txt",
    "feed_info.txt",
    "routes.txt",
    "shapes.txt",
    "stop_times.txt",
    "stops.txt",
    "trips.txt",
]

# Overpass API (OpenStreetMap, licence ODbL - (c) OpenStreetMap contributors)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Emprise approximative du Maroc (bbox: south, west, north, east)
MOROCCO_BBOX = (21.0, -17.5, 36.0, -0.9)

# GADM v4.1 - decoupage administratif (regions), licence "free for academic/non-commercial use"
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_MAR_shp.zip"
GADM_REGIONS_LAYER = "gadm41_MAR_1"  # niveau 1 = regions

# CRS
CRS_WGS84 = "EPSG:4326"
CRS_MERCHICH = "EPSG:26191"  # Merchich / Nord Maroc - projection metrique pour calculs de distance/surface

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://railgis:railgis@localhost:5432/railgis_maroc"
)

for d in (RAW_DIR, PROCESSED_DIR, GTFS_RAW_DIR, OSM_RAW_DIR, REGIONS_RAW_DIR):
    d.mkdir(parents=True, exist_ok=True)
