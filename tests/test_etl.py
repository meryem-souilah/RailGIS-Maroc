from clean_and_load import _name_tokens, classify_type_ligne, harmonize_name


def test_harmonize_name_strips_and_titlecases():
    assert harmonize_name("  casablanca   voyageurs ") == "Casablanca Voyageurs"


def test_classify_type_ligne_lgv():
    assert classify_type_ligne("Al Boraq") == "LGV"


def test_classify_type_ligne_lgv_from_route_id():
    # Le nom peut etre en anglais ("High Speed") sans mentionner Al Boraq :
    # on se rabat sur le route_id (ex. AL_BORAQ_TNG_CASA).
    assert classify_type_ligne("Tanger - Casablanca (High Speed)", "AL_BORAQ_TNG_CASA") == "LGV"


def test_classify_type_ligne_navette():
    assert classify_type_ligne("Navette Rapide Casablanca") == "navette"


def test_classify_type_ligne_defaults_to_classique():
    assert classify_type_ligne("Marrakech - Fes") == "classique"


def test_name_tokens_ignores_accents_and_boilerplate():
    # 'Rabat-Ville' (GTFS) doit matcher 'Gare Rabat Ville' (OSM) malgre le
    # tiret, la casse et le mot generique 'Gare'.
    assert _name_tokens("Rabat-Ville") == _name_tokens("Gare Rabat Ville")


def test_name_tokens_subset_match_for_partial_names():
    gtfs_tokens = _name_tokens("Taza")
    osm_tokens = _name_tokens("Nouvelle Gare ONCF de Taza")
    assert gtfs_tokens <= osm_tokens
