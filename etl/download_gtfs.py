"""Telecharge le jeu de donnees GTFS ONCF (lignes, arrets, horaires).

Source : github.com/newsbubbles/rail_maroc_oncf (ODbL).
"""
import sys

import requests
from config import GTFS_BASE_URL, GTFS_FILES, GTFS_RAW_DIR


def download_gtfs() -> None:
    for filename in GTFS_FILES:
        url = f"{GTFS_BASE_URL}/{filename}"
        dest = GTFS_RAW_DIR / filename
        print(f"Telechargement {url} -> {dest}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        dest.write_bytes(response.content)
    print(f"GTFS ONCF telecharge dans {GTFS_RAW_DIR} ({len(GTFS_FILES)} fichiers).")


if __name__ == "__main__":
    try:
        download_gtfs()
    except requests.RequestException as exc:
        print(f"Erreur de telechargement GTFS : {exc}", file=sys.stderr)
        sys.exit(1)
