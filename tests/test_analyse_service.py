from services.analyse_service import parse_gtfs_time


def test_parse_gtfs_time_basic():
    assert parse_gtfs_time("08:30:00") == 8 * 3600 + 30 * 60


def test_parse_gtfs_time_past_midnight():
    # Le GTFS autorise des heures > 24:00:00 pour les services de nuit
    assert parse_gtfs_time("25:15:00") == 25 * 3600 + 15 * 60
