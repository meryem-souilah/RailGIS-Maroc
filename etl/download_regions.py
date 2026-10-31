"""Telecharge le decoupage administratif du Maroc (regions, niveau GADM 1).

Source : GADM v4.1 - https://gadm.org (licence : usage academique/non-commercial).
"""
import io
import sys
import zipfile

import requests
from config import GADM_URL, REGIONS_RAW_DIR


def download_regions() -> None:
    print(f"Telechargement {GADM_URL} ...")
    response = requests.get(GADM_URL, timeout=60)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        zf.extractall(REGIONS_RAW_DIR)
    print(f"Decoupage administratif du Maroc extrait dans {REGIONS_RAW_DIR}.")


if __name__ == "__main__":
    try:
        download_regions()
    except requests.RequestException as exc:
        print(f"Erreur de telechargement GADM : {exc}", file=sys.stderr)
        sys.exit(1)
