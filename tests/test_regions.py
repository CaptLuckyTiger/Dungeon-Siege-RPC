from dungeon_rpc.regions import resolve_region_name


def test_region_lookup_known():
    assert resolve_region_name("fh_r1") == "Farmlands"


def test_region_lookup_unknown():
    assert resolve_region_name("unknown_region").startswith("Unknown")
