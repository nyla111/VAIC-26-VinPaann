from types import SimpleNamespace

from app.routes.logistics import _outbound_mode, _weight


def test_outbound_mode_matches_layer1_route_family():
    assert _outbound_mode(SimpleNamespace(selected_route_id="D_WATER_VIA_CT")) == "water"
    assert _outbound_mode(SimpleNamespace(selected_route_id="E_ROAD_WATER_VIA_CT")) == "water"
    assert _outbound_mode(SimpleNamespace(selected_route_id="B_ROAD_VIA_CT")) == "road"
    assert _outbound_mode(SimpleNamespace(selected_route_id=None)) == "road"


def test_actual_arrival_weight_is_preferred_for_capacity_checks():
    order = SimpleNamespace(actual_weight_kg=2200.0, khoi_luong_kg=2000.0)
    assert _weight(order) == 2200.0

    order.actual_weight_kg = None
    assert _weight(order) == 2000.0
