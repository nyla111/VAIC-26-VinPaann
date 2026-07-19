from app.services.map_data import GEOGRAPHIC_POLYLINES


def test_operating_corridors_have_geographic_waypoints():
    assert GEOGRAPHIC_POLYLINES["LEG_CT_HCM_ROAD"]
    assert len(GEOGRAPHIC_POLYLINES["LEG_CT_HCM_ROAD"]) > 2
    assert len(GEOGRAPHIC_POLYLINES["LEG_CT_HCM_WATER"]) > 2


def test_road_and_water_corridors_are_not_identical():
    assert GEOGRAPHIC_POLYLINES["LEG_CT_HCM_ROAD"] != GEOGRAPHIC_POLYLINES["LEG_CT_HCM_WATER"]
